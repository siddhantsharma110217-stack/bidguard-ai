"""Loads the deterministic demo dataset into the database.

Idempotent: re-running returns the existing demo tender/bids rather than
creating duplicates, so the "Load Demo" button is safe to click repeatedly.
Demo bids are matched by bidder name, so a database seeded by an older
single-bidder version gains the missing bidders on the next load.
"""

from sqlalchemy.orm import Session

from app.audit import record_document_loaded
from app.models import Bid, Document, Requirement, Tender
from app.seed import sample_data


def load_demo(db: Session, *, reset: bool = False) -> tuple[Tender, list[Bid]]:
    """Create (or fetch) the demo tender, requirements, bids and documents.

    Returns the tender and its demo bids in `sample_data.BIDDERS` order; the
    first bid is the primary demo bid.
    """
    tender = (
        db.query(Tender)
        .filter(Tender.reference_no == sample_data.TENDER["reference_no"])
        .first()
    )

    if tender and reset:
        db.delete(tender)  # cascades to requirements, bids, documents, evaluations
        db.commit()
        tender = None

    if not tender:
        tender = Tender(**sample_data.TENDER)
        db.add(tender)
        db.flush()

        for spec in sample_data.REQUIREMENTS:
            db.add(Requirement(tender_id=tender.id, **spec))
        db.flush()

    bids: list[Bid] = []
    for bidder in sample_data.BIDDERS:
        bid = (
            db.query(Bid)
            .filter(Bid.tender_id == tender.id, Bid.bidder_name == bidder["bidder_name"])
            .order_by(Bid.id)
            .first()
        )
        if bid is None:
            bid = Bid(tender_id=tender.id, bidder_name=bidder["bidder_name"], status="DRAFT")
            db.add(bid)
            db.flush()
            for spec in bidder["documents"]:
                doc = Document(bid_id=bid.id, **spec)
                db.add(doc)
                db.flush()
                record_document_loaded(db, doc, bid.bidder_name)
        bids.append(bid)

    db.commit()
    db.refresh(tender)
    for bid in bids:
        db.refresh(bid)
    return tender, bids
