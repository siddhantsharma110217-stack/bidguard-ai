import type { Verdict } from '../types'
import { useDemo } from '../context/DemoContext'
import { useEvaluation } from '../context/EvaluationContext'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { VerdictBadge } from '../components/ui/VerdictBadge'
import { RiskBadge, GateBadge } from '../components/ui/StatusBadges'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconBarChart } from '../components/icons'

function formatTimestamp(iso: string | null): string {
  if (!iso) return 'Not recorded'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleString()
}

export function ReportsPage() {
  const { loading: demoLoading, loadDemo } = useDemo()
  const { results, loading, error, running, runError, bidId, run, reload } = useEvaluation()

  if (!demoLoading && bidId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Evaluation Report" />
        <EmptyState
          icon={IconBarChart}
          title="No bid loaded"
          description="Load the sample tender and bidder package to generate a report."
          actionLabel="Load Demo"
          onAction={loadDemo}
          actionLoading={demoLoading}
        />
      </div>
    )
  }

  if (loading || demoLoading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Evaluation Report" />
        <LoadingState label="Preparing report…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Evaluation Report" />
        <ErrorState message={error} onRetry={reload} />
      </div>
    )
  }

  if (!results) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Evaluation Report" />
        <EmptyState
          icon={IconBarChart}
          title="No evaluation has been run yet"
          description="Run a compliance evaluation first — the report is generated from its results."
          actionLabel={running ? 'Evaluating…' : 'Run Compliance Evaluation'}
          onAction={run}
          actionLoading={running}
        >
          {runError && <p className="mt-3 text-sm text-fail">{runError}</p>}
        </EmptyState>
      </div>
    )
  }

  const { summary, tender, bid } = results
  const blocking = results.results.filter(
    (r) => r.obligation === 'MANDATORY' && (r.verdict === 'FAIL' || r.verdict === 'MISSING'),
  )
  const attentionItems = results.results.filter((r) => r.verdict !== 'PASS')
  const overrides = results.results.filter((r) => r.overridden)
  const counts: Record<Verdict, number> = {
    PASS: summary.passed,
    REVIEW: summary.review,
    FAIL: summary.failed,
    MISSING: summary.missing,
  }

  return (
    <div className="report-root flex flex-col gap-6">
      <PageHeader
        title="Evaluation Report"
        description="Compliance evaluation report, generated from the stored evaluation result."
        actions={
          <button
            onClick={() => window.print()}
            className="no-print inline-flex items-center gap-2 rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised"
          >
            Print / Save as PDF
          </button>
        }
      />

      {runError && <p className="no-print text-sm text-fail">{runError}</p>}

      {/* Report masthead */}
      <Card className="report-block p-6">
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-accent">
              BidGuard AI
            </div>
            <h2 className="mt-1 text-lg font-semibold text-text">
              Bid Compliance Evaluation Report
            </h2>
          </div>
          <div className="text-right text-xs text-text-faint">
            <div>Evaluated</div>
            <div className="font-medium text-text-muted">{formatTimestamp(bid.evaluated_at)}</div>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-text-faint">Tender</dt>
            <dd className="mt-0.5 font-medium text-text">{tender.title}</dd>
            <dd className="text-xs text-text-muted">{tender.reference_no}</dd>
          </div>
          <div>
            <dt className="text-text-faint">Bidder</dt>
            <dd className="mt-0.5 font-medium text-text">{bid.bidder_name}</dd>
            <dd className="text-xs text-text-muted">Bid status: {bid.status}</dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap items-end justify-between gap-6 border-t border-border pt-5">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
              Overall Compliance Score
            </div>
            <div className="mt-1 text-4xl font-semibold tabular-nums text-text">
              {summary.overall_compliance}%
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-text-faint">Risk</div>
              <div className="mt-1.5">
                <RiskBadge band={summary.risk_band} score={summary.risk_score} />
              </div>
            </div>
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
                Responsiveness
              </div>
              <div className="mt-1.5">
                <GateBadge status={summary.gate_status} />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Requirement summary */}
      <Card className="report-block p-5">
        <h3 className="text-sm font-semibold text-text">Requirement Summary</h3>
        <div className="mt-3 grid grid-cols-3 gap-4 text-sm sm:grid-cols-5">
          <div>
            <div className="text-xs text-text-faint">Total</div>
            <div className="mt-1.5 text-xl font-semibold tabular-nums text-text">
              {summary.total_requirements}
            </div>
          </div>
          {(['PASS', 'REVIEW', 'FAIL', 'MISSING'] as Verdict[]).map((v) => (
            <div key={v}>
              <VerdictBadge verdict={v} />
              <div className="mt-1.5 text-xl font-semibold tabular-nums text-text">{counts[v]}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Officer overrides */}
      <Card className="report-block p-5">
        <h3 className="text-sm font-semibold text-text">Officer Overrides ({overrides.length})</h3>
        {overrides.length === 0 ? (
          <p className="mt-1 text-sm text-text-muted">
            No verdicts were overridden — every finding below is the system's verdict.
          </p>
        ) : (
          <>
            <p className="mt-1 text-sm text-text-muted">
              Verdicts changed by an evaluating officer. Scores and responsiveness above use the
              officer's verdict; each change is recorded in the tamper-evident audit log.
            </p>
            <ul className="mt-3 space-y-3">
              {overrides.map((r) => (
                <li
                  key={r.requirement_id}
                  className="report-item border-t border-border pt-3 text-sm first:border-0 first:pt-0"
                >
                  <div className="font-medium text-text">
                    {r.requirement_code} — {r.requirement_title}
                  </div>
                  <p className="mt-1 text-text-muted">
                    <span className="font-medium text-text">
                      {r.system_verdict} → {r.verdict}
                    </span>
                    , {r.override_reason}
                  </p>
                  <p className="mt-1 text-xs text-text-faint">
                    Overridden by {r.officer_name}
                    {r.overridden_at && ` on ${formatTimestamp(r.overridden_at)}`}
                  </p>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      {/* Blocking requirements */}
      <Card className="report-block border-fail/30 p-5">
        <h3 className="text-sm font-semibold text-text">
          Blocking Requirements ({summary.blocking_requirements})
        </h3>
        {blocking.length === 0 ? (
          <p className="mt-1 text-sm text-text-muted">
            No mandatory requirement failures — the bid is responsive.
          </p>
        ) : (
          <>
            <p className="mt-1 text-sm text-text-muted">
              Mandatory requirements not met. These determine the{' '}
              {summary.gate_status.replace('_', '-')} status.
            </p>
            <ul className="mt-3 space-y-3">
              {blocking.map((r) => (
                <li key={r.requirement_id} className="flex items-start gap-3 text-sm">
                  <span className="mt-0.5 shrink-0">
                    <VerdictBadge verdict={r.verdict} />
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium text-text">
                      {r.requirement_code} — {r.requirement_title}
                    </div>
                    <p className="mt-0.5 text-xs text-text-muted">{r.explanation}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      {/* Detailed findings */}
      <Card className="report-block overflow-x-auto">
        <div className="border-b border-border p-5 pb-3">
          <h3 className="text-sm font-semibold text-text">Detailed Findings</h3>
        </div>
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Requirement</th>
              <th className="px-4 py-3">Verdict</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Evidence / Source</th>
              <th className="px-4 py-3">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {results.results.map((r) => (
              <tr key={r.requirement_id} className="border-b border-border align-top last:border-0">
                <td className="px-4 py-3 font-medium tabular-nums text-text">
                  {r.requirement_code}
                </td>
                <td className="px-4 py-3 font-medium text-text">{r.requirement_title}</td>
                <td className="px-4 py-3">
                  <VerdictBadge verdict={r.verdict} />
                  {r.overridden && (
                    <div className="mt-1 text-[11px] whitespace-nowrap text-text-faint">
                      {r.system_verdict} → {r.verdict} (officer)
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 tabular-nums text-text">{r.score.toFixed(0)}</td>
                <td className="px-4 py-3 text-xs text-text-muted">
                  {r.evidence ? (
                    <>
                      <div className="text-text">{r.evidence}</div>
                      <div className="mt-0.5 text-text-faint">
                        {r.source_document}
                        {r.source_page > 0 && ` · p.${r.source_page}`}
                      </div>
                    </>
                  ) : (
                    'No evidence found'
                  )}
                </td>
                <td className="px-4 py-3 tabular-nums text-text-muted">
                  {Math.round(r.confidence * 100)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Risk & attention items */}
      <Card className="report-block p-5">
        <h3 className="text-sm font-semibold text-text">Risk &amp; Attention Items</h3>
        <p className="mt-1 text-sm text-text-muted">
          Every non-PASS finding, with the reason and the recommended follow-up.
        </p>

        {attentionItems.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">
            No attention items — every requirement passed.
          </p>
        ) : (
          <ul className="mt-4 space-y-4">
            {attentionItems.map((r) => (
              <li
                key={r.requirement_id}
                className="report-item border-t border-border pt-4 first:border-0 first:pt-0"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <VerdictBadge verdict={r.verdict} />
                  <span className="font-medium text-text">
                    {r.requirement_code} — {r.requirement_title}
                  </span>
                  <span className="text-xs text-text-faint">
                    ({r.obligation.toLowerCase()}, decided by{' '}
                    {r.overridden ? `officer ${r.officer_name}` : r.decision_source})
                  </span>
                </div>
                <p className="mt-1 text-sm text-text-muted">{r.explanation}</p>
                <p className="mt-1 text-xs text-text-faint">
                  Evidence:{' '}
                  {r.evidence ? `Found in ${r.source_document}` : 'Not found in submitted package'}
                </p>
                <p className="mt-1 text-xs font-medium text-accent">
                  Recommended action: {r.recommended_action}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
