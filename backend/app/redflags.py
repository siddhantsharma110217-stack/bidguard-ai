"""Cross-bidder red-flag detection for one tender.

Two families of flags:

* Possible collusion — two different bidders declare the same phone, email,
  registered address or bank account, or submit documents whose text is more
  than 90% similar.
* Inconsistent treatment — the same requirement failed the same rule for
  several bidders (identical system verdict), yet their final decisions
  differ, e.g. one delivery failure overridden to PASS while another stays FAIL.

Every flag is an indicator for the officer to look into, never a finding:
the API and UI always carry `DISCLAIMER` alongside the flags.

Detection works on plain snapshots (`BidSnapshot`) so it can be tested
without a database; `app.api.redflags` builds them from stored rows.
"""

import re
from dataclasses import dataclass, field
from itertools import combinations

from rapidfuzz import fuzz

DISCLAIMER = "red flag for review — not proof of wrongdoing"

# Text similarity above this (rapidfuzz ratio, 0-100) is flagged.
SIMILARITY_THRESHOLD = 90.0

# Documents with less text than this are skipped for similarity. Short
# standard forms (e.g. a one-line OEM authorisation issued by the same
# manufacturer to every bidder) are near-identical by design and would
# otherwise drown the officer in false positives.
MIN_SIMILARITY_TEXT_LENGTH = 200

# System verdicts meaning "the bidder's evidence failed the rule".
FAILED_VERDICTS = ("FAIL", "MISSING")

CONTACT_LABELS = {
    "bidder_phone": "Phone",
    "bidder_email": "Email",
    "bidder_address": "Registered Address",
    "bank_account": "Bank Account",
}


@dataclass
class ContactValue:
    field: str
    value: str
    source_document: str = ""
    source_page: int = 0


@dataclass
class DocumentText:
    document_id: int
    filename: str
    doc_type: str
    text: str


@dataclass
class Decision:
    requirement_id: int
    requirement_code: str
    requirement_title: str
    system_verdict: str
    final_verdict: str
    explanation: str = ""
    override_reason: str = ""
    officer_name: str = ""


@dataclass
class BidSnapshot:
    bid_id: int
    bidder_name: str
    contact: list[ContactValue] = field(default_factory=list)
    documents: list[DocumentText] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalisation — so trivially different spellings still match
# ---------------------------------------------------------------------------

def normalize_contact(field_name: str, value: str) -> str:
    value = value.strip()
    if field_name == "bidder_phone":
        digits = re.sub(r"\D", "", value)
        # Compare national numbers: drop an Indian +91 / leading 0 prefix.
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        return digits.lstrip("0")
    if field_name == "bidder_email":
        return value.lower()
    if field_name == "bank_account":
        # The account number identifies the account; bank name formatting varies.
        numbers = re.findall(r"\d{6,}", value)
        return max(numbers, key=len) if numbers else re.sub(r"\W", "", value).upper()
    return re.sub(r"[\W_]+", " ", value.lower()).strip()


def _bidder(bid: BidSnapshot) -> dict:
    return {"bid_id": bid.bid_id, "bidder_name": bid.bidder_name}


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def shared_contact_flags(bids: list[BidSnapshot]) -> list[dict]:
    flags = []
    for field_name, label in CONTACT_LABELS.items():
        groups: dict[str, list[tuple[BidSnapshot, ContactValue]]] = {}
        for bid in bids:
            for c in bid.contact:
                if c.field != field_name or not c.value.strip():
                    continue
                key = normalize_contact(field_name, c.value)
                if key:
                    groups.setdefault(key, []).append((bid, c))

        for entries in groups.values():
            if len({b.bid_id for b, _ in entries}) < 2:
                continue
            flags.append(
                {
                    "kind": "SHARED_CONTACT",
                    "category": "POSSIBLE_COLLUSION",
                    "title": f"Shared {label.lower()}",
                    "summary": (
                        f"{len(entries)} bidders declare the same {label.lower()} "
                        "while bidding as separate firms."
                    ),
                    "bidders": [_bidder(b) for b, _ in entries],
                    "evidence": [
                        {
                            "bid_id": b.bid_id,
                            "bidder_name": b.bidder_name,
                            "label": label,
                            "value": c.value,
                            "source_document": c.source_document,
                            "source_page": c.source_page,
                            "detail": "",
                        }
                        for b, c in entries
                    ],
                    "similarity": None,
                    "requirement_code": "",
                }
            )
    return flags


def similar_document_flags(bids: list[BidSnapshot]) -> list[dict]:
    flags = []
    for a, b in combinations(bids, 2):
        for da in a.documents:
            for db in b.documents:
                if da.doc_type != db.doc_type:
                    continue
                if min(len(da.text), len(db.text)) < MIN_SIMILARITY_TEXT_LENGTH:
                    continue
                score = round(fuzz.ratio(da.text, db.text), 1)
                if score <= SIMILARITY_THRESHOLD:
                    continue
                flags.append(
                    {
                        "kind": "SIMILAR_DOCUMENTS",
                        "category": "POSSIBLE_COLLUSION",
                        "title": f"Near-identical {da.doc_type.replace('_', ' ').lower()}",
                        "summary": (
                            f"Document text is {score}% similar between two different "
                            f"bidders (threshold {SIMILARITY_THRESHOLD:g}%)."
                        ),
                        "bidders": [_bidder(a), _bidder(b)],
                        "evidence": [
                            {
                                "bid_id": bid.bid_id,
                                "bidder_name": bid.bidder_name,
                                "label": doc.filename,
                                "value": doc.text[:300],
                                "source_document": doc.filename,
                                "source_page": 0,
                                "detail": f"{score}% similar",
                            }
                            for bid, doc in ((a, da), (b, db))
                        ],
                        "similarity": score,
                        "requirement_code": "",
                    }
                )
    return flags


def inconsistent_treatment_flags(bids: list[BidSnapshot]) -> list[dict]:
    # (requirement, system verdict) -> every bidder whose evidence failed it
    groups: dict[tuple[int, str], list[tuple[BidSnapshot, Decision]]] = {}
    for bid in bids:
        for d in bid.decisions:
            if d.system_verdict in FAILED_VERDICTS:
                groups.setdefault((d.requirement_id, d.system_verdict), []).append((bid, d))

    flags = []
    for (_, system_verdict), entries in groups.items():
        finals = {d.final_verdict for _, d in entries}
        if len(entries) < 2 or len(finals) < 2:
            continue
        first = entries[0][1]
        flags.append(
            {
                "kind": "INCONSISTENT_TREATMENT",
                "category": "INCONSISTENT_TREATMENT",
                "title": f"{first.requirement_code} — {first.requirement_title}",
                "summary": (
                    f"{len(entries)} bidders failed this requirement's rule "
                    f"(system verdict {system_verdict}) but received different final "
                    f"decisions: {', '.join(sorted(finals))}."
                ),
                "bidders": [_bidder(b) for b, _ in entries],
                "evidence": [
                    {
                        "bid_id": b.bid_id,
                        "bidder_name": b.bidder_name,
                        "label": f"{d.system_verdict} → {d.final_verdict}",
                        "value": d.explanation,
                        "source_document": "",
                        "source_page": 0,
                        "detail": (
                            f"Overridden by {d.officer_name}: {d.override_reason}"
                            if d.final_verdict != d.system_verdict
                            else "System verdict kept"
                        ),
                    }
                    for b, d in entries
                ],
                "similarity": None,
                "requirement_code": first.requirement_code,
            }
        )
    return flags


def detect_red_flags(bids: list[BidSnapshot]) -> list[dict]:
    return (
        shared_contact_flags(bids)
        + similar_document_flags(bids)
        + inconsistent_treatment_flags(bids)
    )
