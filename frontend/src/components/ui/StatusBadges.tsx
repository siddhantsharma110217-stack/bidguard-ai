import type { GateStatus, RiskBand } from '../../types'
import { Badge, type BadgeTone } from './Badge'

const RISK_TONE: Record<RiskBand, BadgeTone> = {
  LOW: 'pass',
  MEDIUM: 'review',
  HIGH: 'fail',
  CRITICAL: 'fail',
}

export function RiskBadge({ band, score }: { band: RiskBand; score?: number }) {
  return (
    <Badge tone={RISK_TONE[band]}>
      {band}
      {score != null && <span className="tabular-nums">({score})</span>}
    </Badge>
  )
}

export function GateBadge({ status }: { status: GateStatus }) {
  return (
    <Badge tone={status === 'RESPONSIVE' ? 'pass' : 'fail'}>
      {status.replace('_', '-')}
    </Badge>
  )
}
