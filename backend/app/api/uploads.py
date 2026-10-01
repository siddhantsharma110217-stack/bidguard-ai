"""Upload a new bid (bidder name + PDF files) against a tender.

Each file is validated (PDF only, size limit, must open), stored under
`storage/bids/` with a cleaned filename, read page by page, fingerprinted
from its stored bytes, and logged as a DOCUMENT_LOADED audit event. Evidence
is then extracted (AI or rule-based) into the same per-field shape the demo
documents use, so evaluation, overrides, the audit log and Red Flags all
treat an uploaded bid exactly like a demo bidder.
"""

import hashlib
import re
import secrets
import shutil
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.bids import document_out
from app.api.tenders import get_tender_or_404
from app.audit import record_document_loaded
from app.config import settings
from app.db import get_db
from app.extraction.pdf import InvalidPdf, PdfText, read_pdf
from app.extraction.rules import SourceDoc
from app.extraction.service import MODE_LABELS, classify, extract_bid
from app.models import Bid, Document, Requirement
from app.schemas import BidOut, UploadResultOut

router = APIRouter(prefix="/api/tenders", tags=["uploads"])

MAX_FILES = 20
MAX_NAME_LENGTH = 120


def clean_filename(name: str) -> str:
    """A safe display/storage name: no directories, ASCII only, `.pdf` suffix.

    "../../etc/passwd.pdf" -> "passwd.pdf"; "C:\\bids\\Tech Bid (v2).PDF" ->
    "Tech_Bid_v2.pdf". The caller checks the extension first.
    """
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    stem = base[: -len(".pdf")] if base.lower().endswith(".pdf") else base
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"[._-]{2,}", "_", stem).strip("._-")[:80]
    return f"{stem or 'document'}.pdf"


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def _read_upload(upload: UploadFile, limit: int) -> tuple[str, bytes, PdfText]:
    original = upload.filename or ""
    shown = original.replace("\\", "/").split("/")[-1] or "(unnamed file)"
    if not original.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail=f"'{shown}' is not a PDF. Only PDF files (.pdf) are accepted.",
        )
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                f"'{shown}' is larger than {settings.max_upload_mb} MB. "
                f"The limit is {settings.max_upload_mb} MB per file."
            ),
        )
    if not data:
        raise HTTPException(status_code=422, detail=f"'{shown}' is empty.")
    try:
        text = read_pdf(data)
    except InvalidPdf as exc:
        raise HTTPException(
            status_code=422, detail=f"'{shown}' is not a valid PDF: {exc}."
        ) from exc
    return clean_filename(original), data, text


@router.post("/{tender_id}/bids/upload", response_model=UploadResultOut, status_code=201)
def upload_bid(
    tender_id: int,
    bidder_name: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    tender = get_tender_or_404(tender_id, db)

    name = " ".join(bidder_name.split())
    if not name:
        raise HTTPException(status_code=422, detail="The bidder company name is required.")
    if len(name) > MAX_NAME_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"The bidder company name must be at most {MAX_NAME_LENGTH} characters.",
        )
    clash = (
        db.query(Bid)
        .filter(Bid.tender_id == tender_id, func.lower(Bid.bidder_name) == name.lower())
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"A bid from '{clash.bidder_name}' already exists for this tender.",
        )
    if not files:
        raise HTTPException(status_code=422, detail="Attach at least one PDF file.")
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=422, detail=f"Upload at most {MAX_FILES} files per bid."
        )

    # Validate everything before writing anything.
    limit = settings.max_upload_mb * 1024 * 1024
    parsed = [_read_upload(f, limit) for f in files]

    root = (settings.storage_path / "bids").resolve()
    folder = root / f"bid_upload_{secrets.token_hex(6)}"
    try:
        bid = Bid(tender_id=tender_id, bidder_name=name, status="DRAFT")
        db.add(bid)
        db.flush()

        folder.mkdir(parents=True, exist_ok=False)
        docs: list[Document] = []
        sources: list[SourceDoc] = []
        for i, (filename, data, text) in enumerate(parsed, start=1):
            path = (folder / f"{i:02d}_{filename}").resolve()
            if not path.is_relative_to(root):  # defence in depth
                raise HTTPException(status_code=422, detail="Invalid file name.")
            path.write_bytes(data)

            blank = text.pages_without_text
            doc = Document(
                bid_id=bid.id,
                original_filename=filename,
                storage_path=str(path),
                mime="application/pdf",
                page_count=text.page_count,
                file_size=len(data),
                source="UPLOAD",
                page_texts=text.pages,
                pages_without_text=blank,
                has_text_layer=not blank,
                doc_type=classify(filename, "\n".join(text.pages)),
                doc_type_confidence=0.6,
                classified_by="KEYWORDS",
                fields={},
            )
            db.add(doc)
            docs.append(doc)
            sources.append(SourceDoc(filename, text.pages, blank))
        db.flush()

        requirements = (
            db.query(Requirement)
            .filter(Requirement.tender_id == tender_id)
            .order_by(Requirement.code)
            .all()
        )
        result = extract_bid(requirements, sources)
        per_doc: list[dict] = [{} for _ in docs]
        for field_name, (d_idx, data) in result.fields.items():
            per_doc[d_idx][field_name] = data
        for doc, fields in zip(docs, per_doc):
            doc.fields = fields
            doc.extraction_mode = result.mode
            doc.extraction_note = result.note

        for doc, (_, data, _) in zip(docs, parsed):
            record_document_loaded(db, doc, bid.bidder_name)
            # The fingerprint is taken from the stored file; it must equal
            # the bytes that were received.
            if doc.sha256 != hashlib.sha256(data).hexdigest():
                raise RuntimeError(f"stored file for {doc.original_filename} does not match upload")

        db.commit()
    except Exception:
        db.rollback()
        shutil.rmtree(folder, ignore_errors=True)
        raise

    db.refresh(bid)
    return UploadResultOut(
        bid=BidOut.model_validate(bid),
        tender_id=tender.id,
        extraction_mode=result.mode,
        extraction_label=MODE_LABELS[result.mode],
        extraction_note=result.note,
        documents=[document_out(d) for d in docs],
    )


def remove_upload_files(docs: list[Document]) -> None:
    """Delete stored upload folders (used when the demo is reset)."""
    root = (settings.storage_path / "bids").resolve()
    for doc in docs:
        if doc.source != "UPLOAD" or not doc.storage_path:
            continue
        folder = Path(doc.storage_path).resolve().parent
        if folder.is_relative_to(root) and folder != root:
            shutil.rmtree(folder, ignore_errors=True)
