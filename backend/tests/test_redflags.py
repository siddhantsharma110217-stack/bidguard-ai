"""Cross-bidder red flags: collusion indicators and inconsistent treatment."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Bid, Document, Tender
from app.redflags import (
    DISCLAIMER,
    MIN_SIMILARITY_TEXT_LENGTH,
    BidSnapshot,
    ContactValue,
    Decision,
    DocumentText,
    detect_red_flags,
    normalize_contact,
)
from app.seed import sample_data

TECHNOVA = "TechNova Systems Pvt. Ltd."
APEX = "Apex Infotech Solutions"
BHARAT = "Bharat Digital Technologies Pvt. Ltd."
CRESTLINE = "Crestline Computers LLP"
REASON = "Revised delivery schedule accepted by the committee."

LONG_TEXT = (
    "Processor: Intel Core i5-13420H (13th Gen, 8 cores, up to 4.6 GHz). "
    "Memory: 16 GB DDR5 4800 MHz, upgradable to 32 GB. Storage: 512 GB PCIe "
    "NVMe M.2 SSD. Display: 15.6 inch FHD IPS anti-glare, 250 nits. Operating "
    "System: Windows 11 Pro 64-bit, pre-loaded with OEM licence."
)
assert len(LONG_TEXT) >= MIN_SIMILARITY_TEXT_LENGTH


def _contact(phone, email, address, bank):
    return [
        ContactValue("bidder_phone", phone, "Commercial_Bid.pdf", 1),
        ContactValue("bidder_email", email, "Commercial_Bid.pdf", 1),
        ContactValue("bidder_address", address, "Commercial_Bid.pdf", 1),
        ContactValue("bank_account", bank, "Commercial_Bid.pdf", 1),
    ]


def _decision(system, final, **kw):
    return Decision(
        requirement_id=8,
        requirement_code="REQ-008",
        requirement_title="Delivery Period",
        system_verdict=system,
        final_verdict=final,
        **kw,
    )


def clean_bids() -> list[BidSnapshot]:
    """Three unrelated bidders: distinct contacts, distinct long documents,
    and identical failures treated identically."""
    return [
        BidSnapshot(
            1, "Alpha Ltd.",
            contact=_contact("+91 80 1111 2222", "a@alpha.in", "1 MG Road, Bengaluru", "HDFC A/c 50200011112222"),
            documents=[DocumentText(1, "Technical_Bid.pdf", "TECHNICAL_BID", LONG_TEXT)],
            decisions=[_decision("FAIL", "FAIL")],
        ),
        BidSnapshot(
            2, "Beta Ltd.",
            contact=_contact("+91 22 3333 4444", "b@beta.in", "2 Marine Drive, Mumbai", "ICICI A/c 000400033334444"),
            documents=[DocumentText(2, "Technical_Bid.pdf", "TECHNICAL_BID",
                                    "Quad-core AMD Ryzen 5 7530U, 8 GB LPDDR4X soldered memory, "
                                    "256 GB SATA SSD, 14 inch HD TN panel, Ubuntu 22.04 LTS, two "
                                    "year carry-in warranty, delivery ex-works Chennai within the "
                                    "stated schedule, freight and insurance extra at actuals.")],
            decisions=[_decision("FAIL", "FAIL")],
        ),
        BidSnapshot(
            3, "Gamma Ltd.",
            contact=_contact("+91 11 5555 6666", "c@gamma.in", "3 Connaught Place, New Delhi", "SBI A/c 39100055556666"),
            decisions=[_decision("PASS", "PASS")],
        ),
    ]


# ---------- unit: clean data ----------

def test_clean_data_produces_no_flags():
    assert detect_red_flags(clean_bids()) == []


def test_no_bidders_or_one_bidder_produces_no_flags():
    assert detect_red_flags([]) == []
    assert detect_red_flags(clean_bids()[:1]) == []


# ---------- unit: shared contact details ----------

@pytest.mark.parametrize(
    "field, a, b",
    [
        ("bidder_phone", "+91 98110 36524", "098110-36524"),
        ("bidder_email", "Bids@Example.in", " bids@example.in"),
        ("bidder_address", "B-42, Sector 63, Noida", "b 42 sector 63  noida"),
        ("bank_account", "SBI, A/c No. 39104458821, IFSC SBIN0011235",
         "State Bank of India A/c 39104458821"),
    ],
)
def test_normalisation_matches_formatting_variants(field, a, b):
    assert normalize_contact(field, a) == normalize_contact(field, b)


@pytest.mark.parametrize(
    "field, label",
    [
        ("bidder_phone", "Shared phone"),
        ("bidder_email", "Shared email"),
        ("bidder_address", "Shared registered address"),
        ("bank_account", "Shared bank account"),
    ],
)
def test_each_shared_contact_field_is_flagged(field, label):
    bids = clean_bids()
    shared = next(c for c in bids[0].contact if c.field == field)
    bids[2].contact = [
        ContactValue(field, shared.value, "Covering_Letter.pdf", 2) if c.field == field else c
        for c in bids[2].contact
    ]
    flags = detect_red_flags(bids)
    assert len(flags) == 1
    f = flags[0]
    assert (f["kind"], f["category"], f["title"]) == ("SHARED_CONTACT", "POSSIBLE_COLLUSION", label)
    assert [b["bidder_name"] for b in f["bidders"]] == ["Alpha Ltd.", "Gamma Ltd."]
    assert [e["source_document"] for e in f["evidence"]] == ["Commercial_Bid.pdf", "Covering_Letter.pdf"]
    assert all(e["value"] == shared.value for e in f["evidence"])


def test_three_bidders_sharing_a_phone_is_one_flag():
    bids = clean_bids()
    for b in bids:
        b.contact = [c for c in b.contact if c.field != "bidder_phone"]
        b.contact.append(ContactValue("bidder_phone", "+91 90000 00001"))
    flags = detect_red_flags(bids)
    assert len(flags) == 1
    assert len(flags[0]["bidders"]) == 3


def test_blank_contact_values_are_not_a_match():
    bids = clean_bids()
    for b in bids:
        b.contact = [ContactValue("bidder_email", "  ")]
    assert detect_red_flags(bids) == []


# ---------- unit: document similarity ----------

def test_near_identical_documents_are_flagged():
    bids = clean_bids()
    copied = LONG_TEXT.replace("250 nits", "300 nits")  # a tiny edit
    bids[1].documents = [DocumentText(9, "Tech_Proposal.pdf", "TECHNICAL_BID", copied)]
    flags = detect_red_flags(bids)
    assert len(flags) == 1
    f = flags[0]
    assert f["kind"] == "SIMILAR_DOCUMENTS"
    assert f["similarity"] > 90
    assert {e["source_document"] for e in f["evidence"]} == {"Technical_Bid.pdf", "Tech_Proposal.pdf"}
    assert [b["bidder_name"] for b in f["bidders"]] == ["Alpha Ltd.", "Beta Ltd."]


def test_similarity_at_or_below_threshold_is_not_flagged():
    bids = clean_bids()
    # Rewrite roughly a fifth of the text: clearly related, but not >90%.
    half = len(LONG_TEXT) // 5
    bids[1].documents = [DocumentText(9, "T.pdf", "TECHNICAL_BID", "x" * half + LONG_TEXT[half:])]
    assert detect_red_flags(bids) == []


def test_short_boilerplate_documents_are_not_compared():
    bids = clean_bids()
    form = "Manufacturer Authorization Form issued for Bid No. GEM/2026/B/4471902."
    bids[0].documents.append(DocumentText(5, "OEM.pdf", "OEM_AUTHORIZATION", form))
    bids[1].documents.append(DocumentText(6, "OEM.pdf", "OEM_AUTHORIZATION", form))
    assert detect_red_flags(bids) == []


def test_documents_of_different_types_are_not_compared():
    bids = clean_bids()
    bids[1].documents = [DocumentText(9, "Warranty.pdf", "WARRANTY_CERTIFICATE", LONG_TEXT)]
    assert detect_red_flags(bids) == []


# ---------- unit: inconsistent treatment ----------

def test_override_of_one_identical_failure_is_flagged():
    bids = clean_bids()
    bids[0].decisions = [
        _decision("FAIL", "PASS", explanation="45 days > 30", override_reason=REASON, officer_name="A. Sharma")
    ]
    flags = detect_red_flags(bids)
    assert len(flags) == 1
    f = flags[0]
    assert (f["kind"], f["category"]) == ("INCONSISTENT_TREATMENT", "INCONSISTENT_TREATMENT")
    assert f["requirement_code"] == "REQ-008"
    assert [b["bidder_name"] for b in f["bidders"]] == ["Alpha Ltd.", "Beta Ltd."]
    by_name = {e["bidder_name"]: e for e in f["evidence"]}
    assert by_name["Alpha Ltd."]["label"] == "FAIL → PASS"
    assert REASON in by_name["Alpha Ltd."]["detail"]
    assert by_name["Beta Ltd."]["label"] == "FAIL → FAIL"
    assert by_name["Beta Ltd."]["detail"] == "System verdict kept"


def test_same_override_for_every_identical_failure_is_consistent():
    bids = clean_bids()
    for b in bids[:2]:
        b.decisions = [_decision("FAIL", "PASS", override_reason=REASON, officer_name="A. Sharma")]
    assert detect_red_flags(bids) == []


def test_different_system_verdicts_are_not_compared():
    """A PASS bidder and a FAIL bidder did not fail the same rule."""
    bids = clean_bids()
    bids[1].decisions = [_decision("MISSING", "MISSING")]
    bids[0].decisions = [_decision("FAIL", "REVIEW", override_reason=REASON, officer_name="X")]
    assert detect_red_flags(bids) == []


# ---------- API against the four-bidder demo ----------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def demo(client):
    loaded = client.post("/api/demo/load", params={"reset": True}).json()
    return {**loaded, "by_name": {b["bidder_name"]: b["id"] for b in loaded["bids"]}}


def _flags(client, demo):
    resp = client.get(f"/api/tenders/{demo['tender']['id']}/red-flags")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_demo_flags_only_the_two_bidders_sharing_details(client, demo):
    body = _flags(client, demo)
    assert body["disclaimer"] == DISCLAIMER == "red flag for review — not proof of wrongdoing"
    assert [b["bidder_name"] for b in body["bidders"]] == [TECHNOVA, APEX, BHARAT, CRESTLINE]
    assert body["total_flags"] == 2

    titles = sorted(f["title"] for f in body["flags"])
    assert titles == ["Shared bank account", "Shared phone"]
    for f in body["flags"]:
        assert f["category"] == "POSSIBLE_COLLUSION"
        assert {b["bidder_name"] for b in f["bidders"]} == {APEX, CRESTLINE}
        assert len({e["value"] for e in f["evidence"]}) == 1
        assert all(e["source_document"] == "Commercial_Bid.pdf" for e in f["evidence"])
        assert all(e["source_page"] > 0 for e in f["evidence"])

    involved = {b["bidder_name"] for f in body["flags"] for b in f["bidders"]}
    assert TECHNOVA not in involved and BHARAT not in involved


def test_demo_sample_data_shares_exactly_phone_and_bank_between_apex_and_crestline():
    """Guard the sample data itself: two bidders share details, two are clean."""
    values: dict[str, dict[str, str]] = {}
    for b in sample_data.BIDDERS:
        for d in b["documents"]:
            for f in sample_data.CONTACT_FIELDS:
                if f in d["fields"]:
                    values.setdefault(f, {})[b["bidder_name"]] = d["fields"][f]["value"]
    for f, by_bidder in values.items():
        shared = {n for n, v in by_bidder.items() if list(by_bidder.values()).count(v) > 1}
        expected = {APEX, CRESTLINE} if f in ("bidder_phone", "bank_account") else set()
        assert shared == expected, f


def test_override_creates_and_resolves_inconsistent_treatment(client, demo):
    for bid_id in demo["by_name"].values():
        assert client.post("/api/evaluations", json={"bid_id": bid_id}).status_code == 201
    assert _flags(client, demo)["total_flags"] == 2  # evaluating alone adds nothing

    req_008 = next(
        r["requirement_id"]
        for r in client.get(f"/api/evaluations/{demo['by_name'][TECHNOVA]}/results").json()["results"]
        if r["requirement_code"] == "REQ-008"
    )

    def override(name):
        resp = client.post(
            f"/api/evaluations/{demo['by_name'][name]}/overrides",
            json={
                "requirement_id": req_008,
                "verdict": "PASS",
                "reason_category": "BIDDER_CLARIFICATION",
                "reason": REASON,
                "officer_name": "A. Sharma",
            },
        )
        assert resp.status_code == 201, resp.text

    override(TECHNOVA)
    body = _flags(client, demo)
    inconsistent = [f for f in body["flags"] if f["kind"] == "INCONSISTENT_TREATMENT"]
    assert len(inconsistent) == 1
    f = inconsistent[0]
    assert f["requirement_code"] == "REQ-008"
    assert {b["bidder_name"] for b in f["bidders"]} == {TECHNOVA, APEX}
    by_name = {e["bidder_name"]: e for e in f["evidence"]}
    assert by_name[TECHNOVA]["label"] == "FAIL → PASS"
    assert "A. Sharma" in by_name[TECHNOVA]["detail"] and REASON in by_name[TECHNOVA]["detail"]
    assert "(Clarification received from bidder)" in by_name[TECHNOVA]["detail"]
    assert by_name[APEX]["label"] == "FAIL → FAIL"
    assert "45" in by_name[TECHNOVA]["value"] and "40" in by_name[APEX]["value"]

    # Treating Apex's identical failure the same way resolves it.
    override(APEX)
    kinds = [f["kind"] for f in _flags(client, demo)["flags"]]
    assert "INCONSISTENT_TREATMENT" not in kinds


def test_copied_document_from_another_bidder_is_flagged(client, demo, db):
    bharat = next(b for b in sample_data.BIDDERS if b["bidder_name"] == BHARAT)
    tech = copy.deepcopy(next(d for d in bharat["documents"] if d["doc_type"] == "TECHNICAL_BID"))
    bid = Bid(tender_id=demo["tender"]["id"], bidder_name="Copycat Traders")
    db.add(bid)
    db.flush()
    db.add(Document(bid_id=bid.id, **tech))
    db.commit()

    sim = [f for f in _flags(client, demo)["flags"] if f["kind"] == "SIMILAR_DOCUMENTS"]
    assert len(sim) == 1
    assert {b["bidder_name"] for b in sim[0]["bidders"]} == {BHARAT, "Copycat Traders"}
    assert sim[0]["similarity"] == 100.0


def test_clean_tender_returns_no_flags(client, db):
    """TechNova and Bharat share nothing: a tender with only them is clean."""
    tender = Tender(title="Clean tender", reference_no="CLEAN-001", status="READY")
    db.add(tender)
    db.flush()
    for b in sample_data.BIDDERS:
        if b["bidder_name"] not in (TECHNOVA, BHARAT):
            continue
        bid = Bid(tender_id=tender.id, bidder_name=b["bidder_name"])
        db.add(bid)
        db.flush()
        for spec in b["documents"]:
            db.add(Document(bid_id=bid.id, **spec))
    db.commit()
    try:
        body = client.get(f"/api/tenders/{tender.id}/red-flags").json()
        assert body["total_flags"] == 0
        assert body["flags"] == []
        assert len(body["bidders"]) == 2
    finally:
        db.delete(tender)
        db.commit()


def test_unknown_tender_is_404(client):
    resp = client.get("/api/tenders/999999/red-flags")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
