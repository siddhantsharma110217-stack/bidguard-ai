import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHealth } from '../api/client'
import type { HealthStatus } from '../types'
import { useDemo } from '../context/DemoContext'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { StatTile } from '../components/ui/StatTile'
import { IconDot, IconSpinner } from '../components/icons'

type ConnectionState = 'checking' | 'online' | 'offline'

export function DashboardPage() {
  const [state, setState] = useState<ConnectionState>('checking')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then((result) => {
        setHealth(result)
        setState('online')
      })
      .catch((err: Error) => {
        setError(err.message)
        setState('offline')
      })
  }, [])

  const { dashboard, loading: demoLoading, error: demoError, loadDemo } = useDemo()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        description="Bid compliance verification overview."
      />

      <div className="grid grid-cols-4 gap-4">
        <StatTile
          label="Active Tenders"
          value={String(dashboard?.active_tenders ?? 0)}
          hint={dashboard?.active_tenders ? 'Loaded and ready' : 'Load a tender to begin'}
        />
        <StatTile
          label="Bids Evaluated"
          value={String(dashboard?.bids_evaluated ?? 0)}
          hint={dashboard?.bids_evaluated ? 'Compliance results available' : 'No evaluations yet'}
        />
        <StatTile
          label="Avg. Compliance"
          value={dashboard?.avg_compliance != null ? `${dashboard.avg_compliance}%` : '—'}
          hint={dashboard?.avg_compliance != null ? 'Across evaluated bids' : 'Awaiting first run'}
        />
        <StatTile
          label="High-Risk Bids"
          value={String(dashboard?.high_risk_bids ?? 0)}
          hint={
            dashboard?.high_risk_bids
              ? 'Non-responsive or elevated risk'
              : 'Awaiting first run'
          }
        />
      </div>

      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">System Foundation</h2>
          {state === 'online' && <Badge tone="pass"><IconDot />Operational</Badge>}
          {state === 'offline' && <Badge tone="fail"><IconDot />Backend unreachable</Badge>}
          {state === 'checking' && <Badge tone="neutral"><IconDot />Checking&hellip;</Badge>}
        </div>

        {state === 'online' && health && (
          <dl className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-text-faint">API status</dt>
              <dd className="mt-0.5 font-medium text-text">{health.status}</dd>
            </div>
            <div>
              <dt className="text-text-faint">AI provider</dt>
              <dd className="mt-0.5 font-medium text-text">{health.ai_provider}</dd>
            </div>
            <div>
              <dt className="text-text-faint">Database</dt>
              <dd className="mt-0.5 font-medium text-text">{health.database_url}</dd>
            </div>
          </dl>
        )}

        {state === 'offline' && (
          <p className="text-sm text-fail">
            Could not reach the backend at <code className="text-text-muted">/api/health</code>
            {error ? ` — ${error}` : ''}. Start it with{' '}
            <code className="text-text-muted">uvicorn app.main:app --reload --port 8000</code>{' '}
            from <code className="text-text-muted">backend/</code>.
          </p>
        )}

        {state === 'checking' && (
          <p className="text-sm text-text-muted">Contacting backend&hellip;</p>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">Demo Workflow</h2>
          {dashboard?.demo_loaded && <Badge tone="accent">Demo data loaded</Badge>}
        </div>

        <p className="text-sm text-text-muted">
          Load the sample tender — <strong className="text-text">Supply of Laptop Computers
          for Government Office</strong> — and a bidder document package from{' '}
          <strong className="text-text">TechNova Systems Pvt. Ltd.</strong>, then run
          compliance evaluation to see PASS / REVIEW / FAIL / MISSING verdicts with full
          evidence and scoring.
        </p>

        {demoError && <p className="mt-3 text-sm text-fail">{demoError}</p>}

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => loadDemo()}
            disabled={demoLoading}
            className="inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-60"
          >
            {demoLoading && <IconSpinner />}
            {dashboard?.demo_loaded ? 'Reload Demo Data' : 'Load Demo'}
          </button>

          {dashboard?.demo_loaded && (
            <nav className="flex items-center gap-1 text-xs text-text-muted">
              <Link to="/requirements" className="rounded px-2 py-1 hover:bg-panel-raised hover:text-text">
                Requirements
              </Link>
              <span className="text-text-faint">→</span>
              <Link to="/documents" className="rounded px-2 py-1 hover:bg-panel-raised hover:text-text">
                Documents
              </Link>
              <span className="text-text-faint">→</span>
              <Link to="/evaluation" className="rounded px-2 py-1 hover:bg-panel-raised hover:text-text">
                Evaluation
              </Link>
              <span className="text-text-faint">→</span>
              <Link to="/compliance" className="rounded px-2 py-1 hover:bg-panel-raised hover:text-text">
                Compliance
              </Link>
              <span className="text-text-faint">→</span>
              <Link to="/reports" className="rounded px-2 py-1 hover:bg-panel-raised hover:text-text">
                Reports
              </Link>
            </nav>
          )}
        </div>
      </Card>
    </div>
  )
}
