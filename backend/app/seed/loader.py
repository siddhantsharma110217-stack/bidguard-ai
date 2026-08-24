"""Loads the deterministic demo dataset into the database.

Idempotent: re-running returns the existing demo tender/bid rather than
creating duplicates, so the "Load Demo" button is safe to click repeatedly.
"""

from sqlalchemy.orm import Session

from app.models import Bid, Document, Requirement, Tender
from app.seed import sample_data


def load_demo(db: Session, *, reset: bool = False) -> tuple[Tender, Bid]:
    """Create (or fetch) the demo tender, requirements, bid and documents."""
    existing = (
        db.query(Tender)
        .filter(Tender.reference_no == sample_data.TENDER["reference_no"])
        .first()
    )

    if existing and reset:
        db.delete(existing)  # cascades to requirements, bids, documents, evaluations
        db.commit()
        existing = None

    if existing:
        bid = db.query(Bid).filter(Bid.tender_id == existing.id).first()
        if bid:
            return existing, bid

    if not existing:
        existing = Tender(**sample_data.TENDER)
        db.add(existing)
        db.flush()

        for spec in sample_data.REQUIREMENTS:
            db.add(Requirement(tender_id=existing.id, **spec))
        db.flush()

    bid = Bid(
        tender_id=existing.id,
        bidder_name=sample_data.BIDDER_NAME,
        status="DRAFT",
    )
    db.add(bid)
    db.flush()

    for spec in sample_data.DOCUMENTS:
        db.add(Document(bid_id=bid.id, **spec))

    db.commit()
    db.refresh(existing)
    db.refresh(bid)
    return existing, bid
