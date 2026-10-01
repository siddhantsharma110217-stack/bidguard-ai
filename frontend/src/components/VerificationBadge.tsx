import type { VerificationStatus } from '../types'
import { VERIFICATION_LABEL, VERIFICATION_TONE } from '../verification'
import { Badge } from './ui/Badge'

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  return <Badge tone={VERIFICATION_TONE[status]}>{VERIFICATION_LABEL[status]}</Badge>
}
