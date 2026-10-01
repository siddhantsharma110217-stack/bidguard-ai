export type ExtractionMode = 'AI' | 'RULES' | 'RULES_FALLBACK'

export interface HealthStatus {
  status: string
  ai_provider: string
  database_url: string
  /** Absent on backends that predate PDF upload. Never includes the API key. */
  extraction_mode?: ExtractionMode
  extraction_label?: string
  extraction_model?: string
  max_upload_mb?: number
}

export type Verdict = 'PASS' | 'REVIEW' | 'FAIL' | 'MISSING'
export type Obligation = 'MANDATORY' | 'DESIRABLE'
export type GateStatus = 'RESPONSIVE' | 'NON_RESPONSIVE'
export type RiskBand = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

/** Free-form tender metadata. Every field is optional: the UI renders a row
 *  only when the backend actually supplies it. */
export interface TenderMeta {
  buyer?: string
  bid_type?: string
  quantity?: number
  [key: string]: unknown
}

export interface Tender {
  id: number
  title: string
  reference_no: string
  filename: string
  status: string
  page_count: number
  uploaded_at: string
  meta: TenderMeta
}

export interface Requirement {
  id: number
  code: string
  category: string
  title: string
  description: string
  obligation: Obligation
  rule_type: string
  weight: number
  source_page: number
  source_clause: string
  expected_condition: string
}

export interface RequirementList {
  tender: Tender
  total: number
  mandatory: number
  desirable: number
  requirements: Requirement[]
}

export interface BidDocument {
  id: number
  original_filename: string
  doc_type: string
  doc_type_confidence: number
  classified_by: string
  page_count: number
  has_text_layer: boolean
  extracted_field_count: number
  /** SHA-256 fingerprint taken when the document was loaded. */
  sha256: string
  /** UPLOAD for uploaded PDFs, SAMPLE for seeded demo documents. */
  source: 'UPLOAD' | 'SAMPLE'
  file_size: number
  pages_without_text: number[]
  /** e.g. "No extractable text — OCR not available"; "" when all pages read. */
  text_status: string
  extraction_mode: ExtractionMode | ''
  extraction_label: string
  extraction_note: string
}

export interface UploadResult {
  bid: Bid
  tender_id: number
  extraction_mode: ExtractionMode
  extraction_label: string
  extraction_note: string
  documents: BidDocument[]
}

export interface Bid {
  id: number
  tender_id: number
  bidder_name: string
  status: string
  compliance_score: number
  risk_score: number
  risk_band: RiskBand
  gate_status: GateStatus
  submitted_at: string
  evaluated_at: string | null
}

/** One bidder contact detail, as extracted from a submitted document. */
export interface ContactField {
  field: string
  label: string
  value: string
  source_document: string
  source_document_id: number
  source_page: number
}

export interface BidDocuments {
  bid: Bid
  tender: Tender
  total: number
  documents: BidDocument[]
  /** Absent from backends that predate contact extraction. */
  contact?: ContactField[]
}

export interface EvaluationResult {
  requirement_id: number
  requirement_code: string
  requirement_title: string
  category: string
  obligation: Obligation
  expected_condition: string
  verdict: Verdict
  score: number
  confidence: number
  evidence: string
  source_document: string
  source_document_id: number | null
  source_page: number
  explanation: string
  recommended_action: string
  decision_source: string
  rule_trace: Record<string, unknown>
  /** How the evidence was obtained; '' for pre-extracted demo data. */
  extraction_method: ExtractionMode | ''
  /** AI mode only: VERIFIED | UNSUPPORTED | VALUE_NOT_IN_QUOTE */
  citation_status: string
  /** `verdict` and `score` are effective values; these describe any override. */
  system_verdict: Verdict
  overridden: boolean
  officer_verdict: Verdict | null
  override_reason: string
  /** Reason category code; '' for overrides made before categories existed. */
  override_category: string
  officer_name: string
  overridden_at: string | null
}

export interface OverrideRequest {
  requirement_id: number
  verdict: Verdict
  reason_category: string
  reason: string
  officer_name: string
}

export interface EvaluationSummary {
  total_requirements: number
  passed: number
  review: number
  failed: number
  missing: number
  overall_compliance: number
  risk_score: number
  risk_band: RiskBand
  gate_status: GateStatus
  blocking_requirements: number
}

export interface EvaluationResults {
  bid: Bid
  tender: Tender
  summary: EvaluationSummary
  results: EvaluationResult[]
}

export interface DemoLoadResult {
  tender: Tender
  /** The primary demo bid (first of `bids`). */
  bid: Bid
  bids: Bid[]
  requirement_count: number
  document_count: number
  bidder_count: number
}

export interface Dashboard {
  active_tenders: number
  bids_evaluated: number
  avg_compliance: number | null
  high_risk_bids: number
  demo_loaded: boolean
  demo_tender_id: number | null
  demo_bid_id: number | null
  /** Every bid on the demo tender, in submission order. */
  demo_bid_ids: number[]
}

export type AuditEventType = 'VERDICT_OVERRIDE' | 'DOCUMENT_LOADED'

export interface AuditEvent {
  id: number
  event_type: AuditEventType
  timestamp: string
  bid_id: number | null
  bidder_name: string
  requirement_id: number | null
  requirement_code: string
  requirement_title: string
  system_verdict: Verdict | ''
  officer_verdict: Verdict | ''
  reason: string
  reason_category: string
  officer_name: string
  document_id: number | null
  document_name: string
  document_sha256: string
  prev_hash: string
  hash: string
}

export interface AuditVerification {
  intact: boolean
  total_events: number
  verified_events: number
  head_hash: string
  first_broken: { id: number; position: number; reason: string } | null
  checked_at: string
}

export interface ApiErrorBody {
  detail?: string
}

export type RedFlagKind = 'SHARED_CONTACT' | 'SIMILAR_DOCUMENTS' | 'INCONSISTENT_TREATMENT'
export type RedFlagCategory = 'POSSIBLE_COLLUSION' | 'INCONSISTENT_TREATMENT'

export interface RedFlagEvidence {
  bid_id: number
  bidder_name: string
  label: string
  value: string
  source_document: string
  source_page: number
  detail: string
}

export interface RedFlag {
  kind: RedFlagKind
  category: RedFlagCategory
  title: string
  summary: string
  bidders: { bid_id: number; bidder_name: string }[]
  evidence: RedFlagEvidence[]
  similarity: number | null
  requirement_code: string
}

export interface RedFlagReport {
  tender: Tender
  /** Always shown with the flags: "red flag for review — not proof of wrongdoing". */
  disclaimer: string
  bidders: { bid_id: number; bidder_name: string; evaluated: boolean }[]
  similarity_threshold: number
  min_similarity_text_length: number
  total_flags: number
  flags: RedFlag[]
}
