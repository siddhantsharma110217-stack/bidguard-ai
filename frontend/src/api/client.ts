import type {
  ApiErrorBody,
  AuthUser,
  DemoAccount,
  LoginResult,
  AuditEvent,
  AuditVerification,
  Bid,
  BidDocuments,
  Dashboard,
  DemoLoadResult,
  EvaluationResults,
  HealthStatus,
  OverrideRequest,
  RedFlagReport,
  ReverifyResult,
  UploadResult,
  RequirementList,
  Tender,
} from '../types'

/** Thrown for any non-2xx response, carrying the backend's own message. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// The session token lives in memory here (AuthProvider also keeps it in
// sessionStorage so a page reload stays logged in). Every request sends it.
let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Called when the backend rejects the session (expired, tampered, ...). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {}
  // FormData bodies set their own multipart Content-Type (with boundary).
  if (!(init?.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`

  let res: Response
  try {
    res = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Could not reach the backend. Is it running?')
  }

  if (!res.ok) {
    // The Vite proxy answers 502/503/504 when the backend process is not
    // listening. Surface that as the actionable cause rather than a bare code.
    let message =
      res.status >= 502 && res.status <= 504
        ? 'Could not reach the backend. Make sure it is running on port 8000.'
        : `Request failed with status ${res.status}.`
    try {
      const body = (await res.json()) as ApiErrorBody
      if (body.detail) message = body.detail
    } catch {
      // response wasn't JSON — keep the message above, never surface raw HTML/stack traces
    }
    if (res.status === 401 && authToken && onUnauthorized) onUnauthorized()
    throw new ApiError(res.status, message)
  }

  return res.json() as Promise<T>
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health')
}

export function getDashboard(): Promise<Dashboard> {
  return request<Dashboard>('/api/dashboard')
}

export function loadDemo(reset = false): Promise<DemoLoadResult> {
  return request<DemoLoadResult>(`/api/demo/load?reset=${reset}`, { method: 'POST' })
}

export function getTender(tenderId: number): Promise<Tender> {
  return request<Tender>(`/api/tenders/${tenderId}`)
}

export function getRequirements(tenderId: number): Promise<RequirementList> {
  return request<RequirementList>(`/api/tenders/${tenderId}/requirements`)
}

/** All bids, or only those submitted against `tenderId`. */
export function listBids(tenderId?: number): Promise<Bid[]> {
  const query = tenderId == null ? '' : `?tender_id=${tenderId}`
  return request<Bid[]>(`/api/bids${query}`)
}

export function getBid(bidId: number): Promise<Bid> {
  return request<Bid>(`/api/bids/${bidId}`)
}

export function getBidDocuments(bidId: number): Promise<BidDocuments> {
  return request<BidDocuments>(`/api/bids/${bidId}/documents`)
}

export function runEvaluation(bidId: number): Promise<EvaluationResults> {
  return request<EvaluationResults>('/api/evaluations', {
    method: 'POST',
    body: JSON.stringify({ bid_id: bidId }),
  })
}

export function getEvaluationResults(bidId: number): Promise<EvaluationResults> {
  return request<EvaluationResults>(`/api/evaluations/${bidId}/results`)
}

export function createOverride(
  bidId: number,
  payload: OverrideRequest,
): Promise<EvaluationResults> {
  return request<EvaluationResults>(`/api/evaluations/${bidId}/overrides`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listAuditEvents(): Promise<AuditEvent[]> {
  return request<AuditEvent[]>('/api/audit/events')
}

export function verifyAuditChain(): Promise<AuditVerification> {
  return request<AuditVerification>('/api/audit/verify', { method: 'POST' })
}

export function getRedFlags(tenderId: number): Promise<RedFlagReport> {
  return request<RedFlagReport>(`/api/tenders/${tenderId}/red-flags`)
}

/** Upload a new bid: the bidder's company name plus one or more PDFs. */
export function uploadBid(
  tenderId: number,
  bidderName: string,
  files: File[],
): Promise<UploadResult> {
  const form = new FormData()
  form.append('bidder_name', bidderName)
  for (const file of files) form.append('files', file, file.name)
  return request<UploadResult>(`/api/tenders/${tenderId}/bids/upload`, {
    method: 'POST',
    body: form,
  })
}

export function login(username: string, password: string): Promise<LoginResult> {
  return request<LoginResult>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getMe(): Promise<AuthUser> {
  return request<AuthUser>('/api/auth/me')
}

export function getDemoAccounts(): Promise<DemoAccount[]> {
  return request<DemoAccount[]>('/api/auth/demo-accounts')
}

/** Re-hash an uploaded file and compare it with its upload fingerprint (officers only). */
export function reverifyDocument(bidId: number, documentId: number): Promise<ReverifyResult> {
  return request<ReverifyResult>(`/api/bids/${bidId}/documents/${documentId}/reverify`, {
    method: 'POST',
  })
}
