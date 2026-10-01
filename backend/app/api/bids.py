import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import append_event, utc_timestamp
from app.auth import current_user, require_officer
from app.db import get_db
from app.models import Bid, Document, Evaluation, Tender, User
from app.schemas import (
    BidCreate,
    BidDocumentsOut,
    BidOut,
    ContactFieldOut,
    DocumentOut,
    ReverifyOut,
    TenderOut,
)
from app.extraction.pdf import NO_TEXT_LABEL
from app.extraction.service import MODE_LABELS
from app.seed.sample_data import CONTACT_FIELDS

router = APIRouter(
    prefix="/api/bids", tags=["bids"], dependencies=[Depends(current_user)]
)


def get_bid_or_404(bid_id: int, db: Session) -> Bid:
    bid = db.get(Bid, bid_id)
    if bid is None:
        raise HTTPException(status_code=404, detail=f"Bid {bid_id} was not found.")
    return bid


def _text_status(doc: Document) -> str:
    blank = doc.pages_without_text or []
    if doc.source != "UPLOAD" or not blank:
        return ""
    if len(blank) == doc.page_count:
        return NO_TEXT_LABEL
    pages = ", ".join(str(p) for p in blank)
    return f"Page{'s' if len(blank) > 1 else ''} {pages}: {NO_TEXT_LABEL}"


def document_out(doc: Document, verification: tuple[str, str] | None = None) -> DocumentOut:
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
        source=doc.source or "SAMPLE",
        file_size=doc.file_size or 0,
        pages_without_text=doc.pages_without_text or [],
        text_status=_text_status(doc),
        extraction_mode=doc.extraction_mode or "",
        extraction_label=MODE_LABELS.get(doc.extraction_mode or "", ""),
        extraction_note=doc.extraction_note or "",
        has_signature_field=doc.has_signature_field,
        reverifiable=doc.source == "UPLOAD",
        last_reverify_status=doc.last_reverify_status or "",
        last_reverified_at=doc.last_reverified_at,
        verification_status=verification[0] if verification else "",
        verification_reason=verification[1] if verification else "",
    )


def contact_details(docs: list[Document]) -> list[ContactFieldOut]:
    """Bidder contact details, each taken from the first document supplying it.

    Documents are searched in id order, matching how the evaluator resolves
    fields, so the result is stable.
    """
    contact: list[ContactFieldOut] = []
    for field, label in CONTACT_FIELDS.items():
        for doc in docs:
            data = (doc.fields or {}).get(field)
            if data and data.get("value"):
                contact.append(
                    ContactFieldOut(
                        field=field,
                        label=label,
                        value=str(data["value"]),
                        source_document=doc.original_filename,
                        source_document_id=doc.id,
                        source_page=int(data.get("page", 0)),
                    )
                )
                break
    return contact


@router.get("", response_model=list[BidOut])
def list_bids(tender_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Bid)
    if tender_id is not None:
        query = query.filter(Bid.tender_id == tender_id)
    return query.order_by(Bid.id).all()


@router.post("", response_model=BidOut, status_code=201, dependencies=[Depends(require_officer)])
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
    # Issuer verification results from the latest evaluation, per document.
    checks = {
        row.verification_document_id: (row.verification_status, row.verification_reason)
        for row in db.query(Evaluation).filter(
            Evaluation.bid_id == bid_id, Evaluation.verification_document_id.isnot(None)
        )
    }
    return BidDocumentsOut(
        bid=BidOut.model_validate(bid),
        tender=TenderOut.model_validate(bid.tender),
        total=len(docs),
        documents=[document_out(d, checks.get(d.id)) for d in docs],
        contact=contact_details(docs),
    )


FILE_CHECK_SOURCE = "Stored file compared with the SHA-256 recorded at upload"
FILE_CHECK_LABELS = {
    "UNCHANGED": "Unchanged since upload",
    "CHANGED": "FILE CHANGED SINCE UPLOAD",
    "FILE_MISSING": "Stored file is missing",
}


@router.post(
    "/{bid_id}/documents/{document_id}/reverify",
    response_model=ReverifyOut,
)
def reverify_document(
    bid_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    """Re-hash an uploaded file and compare it with its upload fingerprint.

    This shows only whether the stored bytes changed since upload; it says
    nothing about whether the document is genuine. Every check is audited.
    """
    bid = get_bid_or_404(bid_id, db)
    doc = db.get(Document, document_id)
    if doc is None or doc.bid_id != bid.id:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found in this bid.")
    if doc.source != "UPLOAD" or not doc.storage_path:
        raise HTTPException(
            status_code=409,
            detail="Only uploaded files can be re-verified; sample documents have no stored file.",
        )

    path = Path(doc.storage_path)
    if path.is_file():
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        status = "UNCHANGED" if current == doc.sha256 else "CHANGED"
    else:
        current, status = "", "FILE_MISSING"

    at = datetime.now(timezone.utc)
    reason = {
        "UNCHANGED": "The stored file's SHA-256 matches the fingerprint recorded at upload.",
        "CHANGED": "The stored file's SHA-256 differs from the fingerprint recorded at upload.",
        "FILE_MISSING": "The stored file could not be found, so it could not be re-hashed.",
    }[status]
    doc.last_reverify_status = status
    doc.last_reverified_at = at
    append_event(
        db,
        "FILE_REVERIFIED",
        timestamp=utc_timestamp(at),
        bid_id=bid.id,
        bidder_name=bid.bidder_name,
        document_id=doc.id,
        document_name=doc.original_filename,
        document_sha256=current,
        check_status=status,
        check_source=FILE_CHECK_SOURCE,
        reason=reason,
        officer_name=officer.full_name,
        officer_username=officer.username,
    )
    db.commit()
    return ReverifyOut(
        document_id=doc.id,
        status=status,
        label=FILE_CHECK_LABELS[status],
        recorded_sha256=doc.sha256 or "",
        current_sha256=current,
        checked_at=utc_timestamp(at),
    )
