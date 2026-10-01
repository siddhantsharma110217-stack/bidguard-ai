"""Tamper-evident audit log and document fingerprints.

Every audit event stores a SHA-256 hash of its own content together with the
previous event's hash, forming a chain. Editing, deleting or re-ordering any
stored event breaks the chain from that point on, which `verify_chain` reports
as the first broken event.

Note: a hash chain on its own cannot detect truncation of the newest events.
Anchoring the latest hash somewhere external (e.g. printing it on the report)
closes that gap.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import AuditEvent, Document

GENESIS_HASH = "0" * 64

# Why an officer overrode a verdict: stored code -> label shown to people.
REASON_CATEGORIES = {
    "BIDDER_CLARIFICATION": "Clarification received from bidder",
    "EVIDENCE_ELSEWHERE": "Evidence found elsewhere in the bid",
    "EXTRACTION_ERROR": "System extraction error",
    "TENDER_CORRIGENDUM": "Tender corrigendum or amendment",
    "COMMITTEE_DECISION": "Committee decision",
    "OTHER": "Other",
}

# Every column the hash covers, i.e. everything except `hash` itself.
HASHED_FIELDS = (
    "id",
    "event_type",
    "timestamp",
    "bid_id",
    "bidder_name",
    "requirement_id",
    "requirement_code",
    "requirement_title",
    "system_verdict",
    "officer_verdict",
    "reason",
    "officer_name",
    "document_id",
    "document_name",
    "document_sha256",
    "prev_hash",
)

# Fields added after events were already being recorded. They join the
# hashed content only when non-empty, so events written before the field
# existed keep verifying. Blanking or adding one later still changes the
# hashed content, so tampering with it is detected either way.
OPTIONAL_HASHED_FIELDS = ("reason_category", "officer_username", "check_status", "check_source")


def _sha256_json(payload: dict) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_event_hash(event: AuditEvent) -> str:
    content = {f: getattr(event, f) for f in HASHED_FIELDS}
    for f in OPTIONAL_HASHED_FIELDS:
        if getattr(event, f):
            content[f] = getattr(event, f)
    return _sha256_json(content)


def utc_timestamp(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def append_event(db: Session, event_type: str, **fields) -> AuditEvent:
    """Add a chained event to the session. The caller commits.

    The id is assigned here (rather than by the database) because it is part
    of the hashed content: the primary key then also guarantees the chain
    can never fork.
    """
    last = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
    fields.setdefault("timestamp", utc_timestamp())

    event = AuditEvent(
        id=(last.id + 1) if last else 1,
        event_type=event_type,
        prev_hash=last.hash if last else GENESIS_HASH,
        **{
            # Explicit defaults so the hashed values are identical before and
            # after the row round-trips through the database.
            "bid_id": None,
            "bidder_name": "",
            "requirement_id": None,
            "requirement_code": "",
            "requirement_title": "",
            "system_verdict": "",
            "officer_verdict": "",
            "reason": "",
            "reason_category": "",
            "officer_name": "",
            "officer_username": "",
            "check_status": "",
            "check_source": "",
            "document_id": None,
            "document_name": "",
            "document_sha256": "",
            **fields,
        },
    )
    event.hash = compute_event_hash(event)
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Recompute every hash in order and report the first broken event."""
    events = db.query(AuditEvent).order_by(AuditEvent.id).all()
    expected_prev = GENESIS_HASH

    for index, event in enumerate(events):
        if event.prev_hash != expected_prev:
            return _broken(
                events, index, event,
                "Previous-hash link does not match the preceding event "
                "(an event was removed, inserted or re-ordered).",
            )
        if compute_event_hash(event) != event.hash:
            return _broken(
                events, index, event,
                "Stored hash does not match the event's content "
                "(the event was modified after it was recorded).",
            )
        expected_prev = event.hash

    return {
        "intact": True,
        "total_events": len(events),
        "verified_events": len(events),
        "head_hash": expected_prev,
        "first_broken": None,
        "checked_at": utc_timestamp(),
    }


def _broken(events: list[AuditEvent], index: int, event: AuditEvent, reason: str) -> dict:
    return {
        "intact": False,
        "total_events": len(events),
        "verified_events": index,
        "head_hash": events[-1].hash,
        "first_broken": {"id": event.id, "position": index + 1, "reason": reason},
        "checked_at": utc_timestamp(),
    }


# ---------------------------------------------------------------------------
# Document fingerprints
# ---------------------------------------------------------------------------

def fingerprint_document(doc: Document) -> str:
    """SHA-256 of the document as loaded.

    Uses the stored file's bytes when one exists on disk. Seeded demo
    documents have no file, so their loaded content (name, classification and
    extracted fields) is hashed canonically instead.
    """
    if doc.storage_path:
        path = Path(doc.storage_path)
        if path.is_file():
            h = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

    return _sha256_json(
        {
            "original_filename": doc.original_filename,
            "mime": doc.mime,
            "page_count": doc.page_count,
            "doc_type": doc.doc_type,
            "has_text_layer": doc.has_text_layer,
            "fields": doc.fields or {},
        }
    )


def record_document_loaded(db: Session, doc: Document, bidder_name: str) -> None:
    """Fingerprint a freshly loaded document and log it in the audit chain."""
    doc.sha256 = fingerprint_document(doc)
    append_event(
        db,
        "DOCUMENT_LOADED",
        bid_id=doc.bid_id,
        bidder_name=bidder_name,
        document_id=doc.id,
        document_name=doc.original_filename,
        document_sha256=doc.sha256,
    )
