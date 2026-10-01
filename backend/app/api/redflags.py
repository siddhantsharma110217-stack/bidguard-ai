"""Cross-bidder red flags for a tender. Detection lives in app.redflags."""

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.bids import contact_details
from app.api.tenders import get_tender_or_404
from app.audit import REASON_CATEGORIES
from app.db import get_db
from app.models import Bid, Document, Evaluation
from app.redflags import (
    CONTACT_LABELS,
    DISCLAIMER,
    MIN_SIMILARITY_TEXT_LENGTH,
    SIMILARITY_THRESHOLD,
    BidSnapshot,
    ContactValue,
    Decision,
    DocumentText,
    detect_red_flags,
)
from app.schemas import RedFlagReportOut, TenderOut

router = APIRouter(prefix="/api/tenders", tags=["red-flags"])


def document_text(doc: Document) -> str:
    """The document's extracted text, without the contact block.

    Uses the PDF text of uploaded documents, or a stored text layer when one
    exists; seeded demo documents have neither, so their extracted field
    snippets stand in for it. Contact fields are compared exactly by the
    shared-contact check instead.
    """
    if doc.page_texts:
        return "\n".join(doc.page_texts)
    if doc.text_path and Path(doc.text_path).is_file():
        return Path(doc.text_path).read_text(encoding="utf-8", errors="ignore")
    return "\n".join(
        str(data.get("snippet", ""))
        for name, data in sorted((doc.fields or {}).items())
        if name not in CONTACT_LABELS and isinstance(data, dict)
    )


def snapshot(bid: Bid, db: Session) -> BidSnapshot:
    docs = db.query(Document).filter(Document.bid_id == bid.id).order_by(Document.id).all()
    rows = (
        db.query(Evaluation)
        .filter(Evaluation.bid_id == bid.id)
        .order_by(Evaluation.id)
        .all()
    )
    return BidSnapshot(
        bid_id=bid.id,
        bidder_name=bid.bidder_name,
        contact=[
            ContactValue(
                field=c.field,
                value=c.value,
                source_document=c.source_document,
                source_page=c.source_page,
            )
            for c in contact_details(docs)
        ],
        documents=[
            DocumentText(
                document_id=d.id,
                filename=d.original_filename,
                doc_type=d.doc_type,
                text=document_text(d),
            )
            for d in docs
        ],
        decisions=[
            Decision(
                requirement_id=r.requirement_id,
                requirement_code=r.requirement.code,
                requirement_title=r.requirement.title,
                system_verdict=r.verdict,
                final_verdict=r.officer_verdict or r.verdict,
                explanation=r.explanation,
                override_reason=r.override_reason or "",
                override_category=REASON_CATEGORIES.get(r.override_category or "", ""),
                officer_name=r.officer_name or "",
            )
            for r in rows
        ],
    )


@router.get("/{tender_id}/red-flags", response_model=RedFlagReportOut)
def get_red_flags(tender_id: int, db: Session = Depends(get_db)):
    tender = get_tender_or_404(tender_id, db)
    bids = db.query(Bid).filter(Bid.tender_id == tender_id).order_by(Bid.id).all()
    snapshots = [snapshot(b, db) for b in bids]
    flags = detect_red_flags(snapshots)
    return RedFlagReportOut(
        tender=TenderOut.model_validate(tender),
        disclaimer=DISCLAIMER,
        bidders=[
            {
                "bid_id": b.id,
                "bidder_name": b.bidder_name,
                "evaluated": bool(s.decisions),
            }
            for b, s in zip(bids, snapshots)
        ],
        similarity_threshold=SIMILARITY_THRESHOLD,
        min_similarity_text_length=MIN_SIMILARITY_TEXT_LENGTH,
        total_flags=len(flags),
        flags=flags,
    )
