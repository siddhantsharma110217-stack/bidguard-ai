import { useEffect, useState } from 'react'
import { getHealth } from '../../api/client'
import type { HealthStatus } from '../../types'
import { Badge } from '../ui/Badge'
import { IconDot } from '../icons'
import { BidderPicker } from './BidderPicker'
import { useAuth } from '../../context/auth'

type ConnectionState = 'checking' | 'online' | 'offline'

export function TopBar() {
  const { user, logout } = useAuth()
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
        {user && (
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <span className="text-xs text-text-muted">
              Logged in as <span className="font-medium text-text">{user.full_name}</span> (
              {user.role})
            </span>
            <button
              onClick={() => logout()}
              className="rounded border border-border-strong px-2 py-1 text-xs font-medium text-text hover:bg-panel-raised"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
