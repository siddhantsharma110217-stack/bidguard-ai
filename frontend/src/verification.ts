import type { BadgeTone } from './components/ui/Badge'
import type { VerificationStatus } from './types'

export const TRUST_HELP =
  "SHA-256 shows the file hasn't changed since it was loaded. Verification checks its details against the issuer's record. Neither proves a document is genuine on its own."

export const VERIFICATION_LABEL: Record<VerificationStatus, string> = {
  VERIFIED: 'Verified',
  UNVERIFIED: 'Unverified',
  VERIFICATION_FAILED: 'Verification failed — officer review required',
  NOT_APPLICABLE: 'Not applicable',
}

export const VERIFICATION_TONE: Record<VerificationStatus, BadgeTone> = {
  VERIFIED: 'pass',
  UNVERIFIED: 'review',
  VERIFICATION_FAILED: 'fail',
  NOT_APPLICABLE: 'neutral',
}

export function formatCheckedAt(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}
