from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


def _as_utc(value: datetime | None) -> str | None:
    """Serialize datetimes with an explicit UTC offset.

    Timestamps are written as UTC, but SQLite discards tzinfo on the way back
    out. Emitting a naive string would make JavaScript's `new Date()` parse it
    as local time and display the wrong moment, so re-attach UTC here.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    reference_no: str
    filename: str
    status: str
    page_count: int
    uploaded_at: datetime
    meta: dict

    @field_serializer("uploaded_at")
    def _ser_uploaded_at(self, value: datetime) -> str | None:
        return _as_utc(value)


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    category: str
    title: str
    description: str
    obligation: str
    rule_type: str
    weight: int
    source_page: int
    source_clause: str
    expected_condition: str = ""


class RequirementListOut(BaseModel):
    tender: TenderOut
    total: int
    mandatory: int
    desirable: int
    requirements: list[RequirementOut]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    doc_type: str
    doc_type_confidence: float
    classified_by: str
    page_count: int
    has_text_layer: bool
    extracted_field_count: int = 0
    sha256: str = ""
    # UPLOAD for user-uploaded PDFs, SAMPLE for seeded demo documents.
    source: str = "SAMPLE"
    file_size: int = 0
    pages_without_text: list[int] = []
    text_status: str = ""  # human-readable, e.g. "No extractable text — OCR not available"
    extraction_mode: str = ""  # AI | RULES | RULES_FALLBACK | "" (pre-extracted demo data)
    extraction_label: str = ""
    extraction_note: str = ""


class ContactFieldOut(BaseModel):
    """One bidder contact detail, with the document it was extracted from."""

    field: str
    label: str
    value: str
    source_document: str
    source_document_id: int
    source_page: int


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_id: int
    bidder_name: str
    status: str
    compliance_score: float
    risk_score: float
    risk_band: str
    gate_status: str
    submitted_at: datetime
    evaluated_at: datetime | None

    @field_serializer("submitted_at", "evaluated_at")
    def _ser_timestamps(self, value: datetime | None) -> str | None:
        return _as_utc(value)


class BidDocumentsOut(BaseModel):
    bid: BidOut
    tender: TenderOut
    total: int
    documents: list[DocumentOut]
    contact: list[ContactFieldOut] = []


class BidCreate(BaseModel):
    tender_id: int
    bidder_name: str


class EvaluationCreate(BaseModel):
    bid_id: int


class ResultOut(BaseModel):
    requirement_id: int
    requirement_code: str
    requirement_title: str
    category: str
    obligation: str
    expected_condition: str
    verdict: str
    score: float
    confidence: float
    evidence: str
    source_document: str
    source_document_id: int | None
    source_page: int
    explanation: str
    recommended_action: str
    decision_source: str
    rule_trace: dict
    # How the evidence was obtained: AI | RULES | RULES_FALLBACK, or "" for
    # the seeded demo data (pre-extracted). citation_status is set in AI mode:
    # VERIFIED | UNSUPPORTED | VALUE_NOT_IN_QUOTE.
    extraction_method: str = ""
    citation_status: str = ""
    # `verdict`/`score` are the effective values; these describe any override.
    system_verdict: str
    overridden: bool = False
    officer_verdict: str | None = None
    override_reason: str = ""
    override_category: str = ""
    officer_name: str = ""
    officer_username: str = ""
    overridden_at: datetime | None = None

    @field_serializer("overridden_at")
    def _ser_overridden_at(self, value: datetime | None) -> str | None:
        return _as_utc(value)


class OverrideCreate(BaseModel):
    """The officer is always the logged-in user; any officer name a client
    sends is ignored (unknown fields are dropped)."""

    requirement_id: int
    verdict: str
    reason_category: str = ""
    reason: str = ""


class SummaryOut(BaseModel):
    total_requirements: int
    passed: int
    review: int
    failed: int
    missing: int
    overall_compliance: float
    risk_score: float
    risk_band: str
    gate_status: str
    blocking_requirements: int


class EvaluationResultsOut(BaseModel):
    bid: BidOut
    tender: TenderOut
    summary: SummaryOut
    results: list[ResultOut]


class DashboardOut(BaseModel):
    active_tenders: int
    bids_evaluated: int
    avg_compliance: float | None
    high_risk_bids: int
    demo_loaded: bool
    demo_tender_id: int | None
    demo_bid_id: int | None
    demo_bid_ids: list[int] = []


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    timestamp: str
    bid_id: int | None
    bidder_name: str
    requirement_id: int | None
    requirement_code: str
    requirement_title: str
    system_verdict: str
    officer_verdict: str
    reason: str
    reason_category: str
    officer_name: str
    officer_username: str
    document_id: int | None
    document_name: str
    document_sha256: str
    prev_hash: str
    hash: str


class BrokenEventOut(BaseModel):
    id: int
    position: int
    reason: str


class AuditVerifyOut(BaseModel):
    intact: bool
    total_events: int
    verified_events: int
    head_hash: str
    first_broken: BrokenEventOut | None
    checked_at: str


class RedFlagBidderOut(BaseModel):
    bid_id: int
    bidder_name: str


class RedFlagEvidenceOut(BaseModel):
    bid_id: int
    bidder_name: str
    label: str
    value: str
    source_document: str
    source_page: int
    detail: str


class RedFlagOut(BaseModel):
    kind: str  # SHARED_CONTACT | SIMILAR_DOCUMENTS | INCONSISTENT_TREATMENT
    category: str  # POSSIBLE_COLLUSION | INCONSISTENT_TREATMENT
    title: str
    summary: str
    bidders: list[RedFlagBidderOut]
    evidence: list[RedFlagEvidenceOut]
    similarity: float | None
    requirement_code: str


class ComparedBidderOut(BaseModel):
    bid_id: int
    bidder_name: str
    evaluated: bool


class RedFlagReportOut(BaseModel):
    tender: TenderOut
    disclaimer: str
    bidders: list[ComparedBidderOut]
    similarity_threshold: float
    min_similarity_text_length: int
    total_flags: int
    flags: list[RedFlagOut]


class UploadResultOut(BaseModel):
    bid: BidOut
    tender_id: int
    extraction_mode: str
    extraction_label: str
    extraction_note: str
    documents: list[DocumentOut]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    full_name: str
    designation: str
    role: str  # OFFICER | REVIEWER


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    expires_at: int  # Unix timestamp
    user: UserOut


class DemoAccountOut(BaseModel):
    username: str
    full_name: str
    designation: str
    role: str
    demo_password: str | None
