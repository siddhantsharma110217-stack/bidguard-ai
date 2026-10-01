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
        from app.api.uploads import remove_upload_files

        remove_upload_files([d for b in tender.bids for d in b.documents])
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
    else:
        # A tender loaded by an older build predates `verification_required`.
        flags = {s["code"]: s.get("verification_required", False) for s in sample_data.REQUIREMENTS}
        for req in tender.requirements:
            req.verification_required = flags.get(req.code, False)

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
        else:
            _refresh_demo_documents(db, bid, bidder["documents"])
        bids.append(bid)

    db.commit()
    db.refresh(tender)
    for bid in bids:
        db.refresh(bid)
    return tender, bids


def _refresh_demo_documents(db: Session, bid: Bid, specs: list[dict]) -> None:
    """Bring a demo bid loaded by an older build up to date with the sample
    data. A changed document is re-fingerprinted and logged as loaded again,
    so the audit log shows when its contents changed. Unchanged documents
    (the normal case) are left alone and log nothing."""
    by_name = {d.original_filename: d for d in bid.documents}
    for spec in specs:
        doc = by_name.get(spec["original_filename"])
        if doc is None:
            doc = Document(bid_id=bid.id, **spec)
            db.add(doc)
            db.flush()
            record_document_loaded(db, doc, bid.bidder_name)
            continue
        if any(getattr(doc, key) != value for key, value in spec.items()):
            for key, value in spec.items():
                setattr(doc, key, value)
            db.flush()
            record_document_loaded(db, doc, bid.bidder_name)
