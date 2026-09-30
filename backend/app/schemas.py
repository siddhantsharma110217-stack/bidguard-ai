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
