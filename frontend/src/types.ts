export interface HealthStatus {
  status: string
  ai_provider: string
  database_url: string
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

export interface BidDocuments {
  bid: Bid
  tender: Tender
  total: number
  documents: BidDocument[]
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
  bid: Bid
  requirement_count: number
  document_count: number
}

export interface Dashboard {
  active_tenders: number
  bids_evaluated: number
  avg_compliance: number | null
  high_risk_bids: number
  demo_loaded: boolean
  demo_tender_id: number | null
  demo_bid_id: number | null
}

export interface ApiErrorBody {
  detail?: string
}
