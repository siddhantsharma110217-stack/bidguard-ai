from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reference_no: Mapped[str] = mapped_column(String, default="")
    filename: Mapped[str] = mapped_column(String, default="")
    storage_path: Mapped[str] = mapped_column(String, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    # UPLOADED | EXTRACTING | READY | FAILED
    uploaded_at: Mapped[datetime] = mapped_column(default=now)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    bids: Mapped[list["Bid"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))

    code: Mapped[str] = mapped_column(String, nullable=False)  # "REQ-001"
    category: Mapped[str] = mapped_column(String, default="TECHNICAL")
    # LEGAL | FINANCIAL | TECHNICAL | COMPLIANCE | DELIVERY
    title: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")

    obligation: Mapped[str] = mapped_column(String, default="MANDATORY")
    # MANDATORY | DESIRABLE

    rule_type: Mapped[str] = mapped_column(String, default="presence")
    rule_params: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_doc_types: Mapped[list] = mapped_column(JSON, default=list)

    weight: Mapped[int] = mapped_column(Integer, default=3)

    source_page: Mapped[int] = mapped_column(Integer, default=0)
    source_char_start: Mapped[int] = mapped_column(Integer, default=0)
    source_char_end: Mapped[int] = mapped_column(Integer, default=0)
    source_clause: Mapped[str] = mapped_column(Text, default="")

    is_human_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    tender: Mapped["Tender"] = relationship(back_populates="requirements")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("tender_id", "code", name="uq_requirement_code"),)


class Bid(Base):
    __tablename__ = "bids"
    # Never reuse the id of a deleted bid: audit events refer to bids by id
    # and outlive them (e.g. across a demo reset).
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"))
    bidder_name: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(default=now)

    status: Mapped[str] = mapped_column(String, default="DRAFT")
    # DRAFT | EVALUATING | EVALUATED | FAILED

    compliance_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_band: Mapped[str] = mapped_column(String, default="LOW")
    # LOW | MEDIUM | HIGH | CRITICAL
    gate_status: Mapped[str] = mapped_column(String, default="RESPONSIVE")
    # RESPONSIVE | NON_RESPONSIVE
    evaluated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    tender: Mapped["Tender"] = relationship(back_populates="bids")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"sqlite_autoincrement": True}  # see Bid

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))

    original_filename: Mapped[str] = mapped_column(String, default="")
    storage_path: Mapped[str] = mapped_column(String, default="")
    mime: Mapped[str] = mapped_column(String, default="application/pdf")
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    doc_type: Mapped[str] = mapped_column(String, default="UNKNOWN")
    doc_type_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classified_by: Mapped[str] = mapped_column(String, default="SIGNATURE")
    # SIGNATURE | AI | SIGNATURE+AI

    has_text_layer: Mapped[bool] = mapped_column(Boolean, default=True)
    text_path: Mapped[str] = mapped_column(String, default="")
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    # SHA-256 fingerprint taken when the document was loaded (see app.audit).
    # For uploaded files it is computed from the stored file's bytes.
    sha256: Mapped[str] = mapped_column(String, default="")

    # Uploaded PDFs (source == "UPLOAD"); seeded demo documents are "SAMPLE".
    source: Mapped[str] = mapped_column(String, default="SAMPLE")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    # Text per page, index 0 = page 1, exactly as PyMuPDF extracted it.
    page_texts: Mapped[list] = mapped_column(JSON, default=list)
    # Page numbers (1-based) with no extractable text, e.g. scanned images.
    pages_without_text: Mapped[list] = mapped_column(JSON, default=list)
    # AI | RULES | RULES_FALLBACK ("" for seeded demo documents)
    extraction_mode: Mapped[str] = mapped_column(String, default="")
    extraction_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=now)

    bid: Mapped["Bid"] = relationship(back_populates="documents")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"))

    verdict: Mapped[str] = mapped_column(String, default="MISSING")
    # PASS | REVIEW | FAIL | MISSING
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    decision_source: Mapped[str] = mapped_column(String, default="RULE")
    # RULE | AI | RULE+AI | HUMAN_REVIEW

    rule_trace: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")

    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_rationale: Mapped[str] = mapped_column(Text, default="")

    # Officer override. `verdict` always keeps the system's verdict; when
    # `officer_verdict` is set it is the effective verdict for scoring/reports.
    officer_verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    override_reason: Mapped[str] = mapped_column(Text, default="")
    # One of app.audit.REASON_CATEGORIES; "" on overrides made before
    # categories existed.
    override_category: Mapped[str] = mapped_column(String, default="")
    officer_name: Mapped[str] = mapped_column(String, default="")
    overridden_at: Mapped[datetime | None] = mapped_column(nullable=True)

    bid: Mapped["Bid"] = relationship(back_populates="evaluations")
    requirement: Mapped["Requirement"] = relationship(back_populates="evaluations")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    page: Mapped[int] = mapped_column(Integer, default=0)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    snippet: Mapped[str] = mapped_column(Text, default="")

    field_name: Mapped[str] = mapped_column(String, default="")
    field_value: Mapped[str] = mapped_column(String, default="")
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="evidence")
    document: Mapped["Document"] = relationship(back_populates="evidence")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))

    stage: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    # PENDING | RUNNING | DONE | FAILED
    message: Mapped[str] = mapped_column(String, default="")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    bid: Mapped["Bid"] = relationship(back_populates="pipeline_runs")


class LLMCache(Base):
    __tablename__ = "llm_cache"

    prompt_hash: Mapped[str] = mapped_column(String, primary_key=True)
    model: Mapped[str] = mapped_column(String, default="")
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))
    html_path: Mapped[str] = mapped_column(String, default="")
    pdf_path: Mapped[str] = mapped_column(String, default="")
    generated_at: Mapped[datetime] = mapped_column(default=now)

    bid: Mapped["Bid"] = relationship(back_populates="reports")


class AuditEvent(Base):
    """One entry in the append-only, hash-chained audit log.

    Deliberately has no foreign keys: audit history must survive the deletion
    of the bid/tender it describes, so names are copied in at write time.
    `hash` covers every other column plus `prev_hash` (see app.audit).
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # VERDICT_OVERRIDE | DOCUMENT_LOADED
    timestamp: Mapped[str] = mapped_column(String, nullable=False)  # ISO-8601 UTC

    bid_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bidder_name: Mapped[str] = mapped_column(String, default="")

    requirement_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirement_code: Mapped[str] = mapped_column(String, default="")
    requirement_title: Mapped[str] = mapped_column(String, default="")
    system_verdict: Mapped[str] = mapped_column(String, default="")
    officer_verdict: Mapped[str] = mapped_column(String, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    reason_category: Mapped[str] = mapped_column(String, default="")
    officer_name: Mapped[str] = mapped_column(String, default="")

    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_name: Mapped[str] = mapped_column(String, default="")
    document_sha256: Mapped[str] = mapped_column(String, default="")

    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
