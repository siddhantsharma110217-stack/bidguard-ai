import type { Verdict } from '../../types'
import { Badge, type BadgeTone } from './Badge'

const VERDICT_TONE: Record<Verdict, BadgeTone> = {
  PASS: 'pass',
  REVIEW: 'review',
  FAIL: 'fail',
  MISSING: 'missing',
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <Badge tone={VERDICT_TONE[verdict]}>{verdict}</Badge>
}
