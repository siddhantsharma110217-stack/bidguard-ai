from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bid, Tender
from app.schemas import BidOut, DashboardOut, TenderOut
from app.seed import sample_data
from app.seed.loader import load_demo

router = APIRouter(prefix="/api", tags=["demo"])


@router.post("/demo/load")
def load_demo_dataset(reset: bool = False, db: Session = Depends(get_db)):
    """Create (or fetch) the deterministic demo tender + bidder package."""
    tender, bid = load_demo(db, reset=reset)
    return {
        "tender": TenderOut.model_validate(tender),
        "bid": BidOut.model_validate(bid),
        "requirement_count": len(sample_data.REQUIREMENTS),
        "document_count": len(sample_data.DOCUMENTS),
    }


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    tenders = db.query(Tender).all()
    bids = db.query(Bid).all()
    evaluated = [b for b in bids if b.status == "EVALUATED"]

    avg = (
        round(sum(b.compliance_score for b in evaluated) / len(evaluated), 1)
        if evaluated
        else None
    )
    high_risk = sum(
        1 for b in evaluated if b.gate_status == "NON_RESPONSIVE" or b.risk_band in ("HIGH", "CRITICAL")
    )

    demo_tender = (
        db.query(Tender)
        .filter(Tender.reference_no == sample_data.TENDER["reference_no"])
        .first()
    )
    demo_bid = (
        db.query(Bid).filter(Bid.tender_id == demo_tender.id).first()
        if demo_tender
        else None
    )

    return DashboardOut(
        active_tenders=len(tenders),
        bids_evaluated=len(evaluated),
        avg_compliance=avg,
        high_risk_bids=high_risk,
        demo_loaded=demo_tender is not None,
        demo_tender_id=demo_tender.id if demo_tender else None,
        demo_bid_id=demo_bid.id if demo_bid else None,
    )
