import { useEffect, useState } from 'react'
import { getHealth } from '../../api/client'
import type { HealthStatus } from '../../types'
import { Badge } from '../ui/Badge'
import { IconDot } from '../icons'
import { BidderPicker } from './BidderPicker'

type ConnectionState = 'checking' | 'online' | 'offline'

export function TopBar() {
  const [state, setState] = useState<ConnectionState>('checking')
  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const result = await getHealth()
        if (!cancelled) {
          setHealth(result)
          setState('online')
        }
      } catch {
        if (!cancelled) {
          setState('offline')
        }
      }
    }

    check()
    const interval = setInterval(check, 10_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <header className="no-print flex h-14 shrink-0 items-center justify-between border-b border-border bg-panel px-6">
      <div className="text-sm text-text-muted">
        AI-Powered Bid Compliance Verification
      </div>

      <div className="flex items-center gap-3">
        <BidderPicker />
        {state === 'checking' && (
          <Badge tone="neutral">
            <IconDot className="animate-pulse" />
            Connecting to backend&hellip;
          </Badge>
        )}
        {state === 'online' && (
          <Badge tone="pass">
            <IconDot />
            Backend online
            {health && (
              <span className="text-text-faint">
                &middot; {health.extraction_label ?? `${health.ai_provider} mode`}
              </span>
            )}
          </Badge>
        )}
        {state === 'offline' && (
          <Badge tone="fail">
            <IconDot />
            Backend unreachable
          </Badge>
        )}
      </div>
    </header>
  )
}
