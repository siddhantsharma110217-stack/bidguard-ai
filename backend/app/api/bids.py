from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bid, Document, Tender
from app.schemas import BidCreate, BidDocumentsOut, BidOut, DocumentOut, TenderOut

router = APIRouter(prefix="/api/bids", tags=["bids"])


def get_bid_or_404(bid_id: int, db: Session) -> Bid:
    bid = db.get(Bid, bid_id)
    if bid is None:
        raise HTTPException(status_code=404, detail=f"Bid {bid_id} was not found.")
    return bid


def _document_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        original_filename=doc.original_filename,
        doc_type=doc.doc_type,
        doc_type_confidence=doc.doc_type_confidence,
        classified_by=doc.classified_by,
        page_count=doc.page_count,
        has_text_layer=doc.has_text_layer,
        extracted_field_count=len(doc.fields or {}),
        sha256=doc.sha256 or "",
    )


@router.get("", response_model=list[BidOut])
def list_bids(db: Session = Depends(get_db)):
    return db.query(Bid).order_by(Bid.id).all()


@router.post("", response_model=BidOut, status_code=201)
def create_bid(payload: BidCreate, db: Session = Depends(get_db)):
    if db.get(Tender, payload.tender_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Tender {payload.tender_id} was not found."
        )
    if not payload.bidder_name.strip():
        raise HTTPException(status_code=422, detail="A bidder name is required.")

    bid = Bid(tender_id=payload.tender_id, bidder_name=payload.bidder_name.strip())
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid


@router.get("/{bid_id}", response_model=BidOut)
def get_bid(bid_id: int, db: Session = Depends(get_db)):
    return get_bid_or_404(bid_id, db)


@router.get("/{bid_id}/documents", response_model=BidDocumentsOut)
def get_bid_documents(bid_id: int, db: Session = Depends(get_db)):
    bid = get_bid_or_404(bid_id, db)
    docs = (
        db.query(Document)
        .filter(Document.bid_id == bid_id)
        .order_by(Document.id)
        .all()
    )
    return BidDocumentsOut(
        bid=BidOut.model_validate(bid),
        tender=TenderOut.model_validate(bid.tender),
        total=len(docs),
        documents=[_document_out(d) for d in docs],
    )
