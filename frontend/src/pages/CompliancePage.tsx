import { useState } from 'react'
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
import { IconShieldCheck, IconSpinner } from '../components/icons'

type FilterOption = 'ALL' | Verdict

const FILTERS: FilterOption[] = ['ALL', 'PASS', 'REVIEW', 'FAIL', 'MISSING']

export function CompliancePage() {
  const { loading: demoLoading, loadDemo } = useDemo()
  const { results, loading, error, running, runError, bidId, run, reload } = useEvaluation()
  const [filter, setFilter] = useState<FilterOption>('ALL')

  if (!demoLoading && bidId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Compliance Summary" />
        <EmptyState
          icon={IconShieldCheck}
          title="No bid loaded"
          description="Load the sample tender and bidder package to see a compliance summary."
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
        <PageHeader title="Compliance Summary" />
        <LoadingState label="Loading compliance results…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Compliance Summary" />
        <ErrorState message={error} onRetry={reload} />
      </div>
    )
  }

  if (!results) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Compliance Summary" />
        <EmptyState
          icon={IconShieldCheck}
          title="No evaluation has been run yet"
          description="Run a compliance evaluation to generate the summary and detailed findings."
          actionLabel={running ? 'Evaluating…' : 'Run Compliance Evaluation'}
          onAction={run}
          actionLoading={running}
        >
          {runError && <p className="mt-3 text-sm text-fail">{runError}</p>}
        </EmptyState>
      </div>
    )
  }

  const { summary } = results
  const blocking = results.results.filter(
    (r) => r.obligation === 'MANDATORY' && (r.verdict === 'FAIL' || r.verdict === 'MISSING'),
  )
  const filtered =
    filter === 'ALL' ? results.results : results.results.filter((r) => r.verdict === filter)

  const counts: Record<FilterOption, number> = {
    ALL: summary.total_requirements,
    PASS: summary.passed,
    REVIEW: summary.review,
    FAIL: summary.failed,
    MISSING: summary.missing,
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Compliance Summary"
        description={`${results.tender.title} — ${results.bid.bidder_name}`}
        actions={
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center gap-2 rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised disabled:opacity-60"
          >
            {running && <IconSpinner />}
            Re-run Evaluation
          </button>
        }
      />

      {runError && <p className="text-sm text-fail">{runError}</p>}

      {/* Headline result */}
      <Card className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
              Overall Compliance
            </div>
            <div className="mt-1 text-5xl font-semibold tabular-nums text-text">
              {summary.overall_compliance}%
            </div>
          </div>

          <div className="flex gap-8">
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

        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-5 sm:grid-cols-4">
          {(['PASS', 'REVIEW', 'FAIL', 'MISSING'] as Verdict[]).map((v) => (
            <div key={v}>
              <VerdictBadge verdict={v} />
              <div className="mt-2 text-2xl font-semibold tabular-nums text-text">{counts[v]}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Blocking requirements */}
      {blocking.length > 0 && (
        <Card className="border-fail/30 p-5">
          <h2 className="text-sm font-semibold text-text">
            Blocking Requirements ({summary.blocking_requirements})
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Mandatory requirements not met — these determine the{' '}
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
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              filter === f
                ? 'border border-accent-border bg-accent-bg text-accent'
                : 'border border-transparent text-text-muted hover:bg-panel-raised hover:text-text'
            }`}
          >
            {f === 'ALL' ? 'All' : f}
            <span className="ml-1.5 tabular-nums text-text-faint">{counts[f]}</span>
          </button>
        ))}
      </div>

      {/* Requirement-level detail */}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
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
            {filtered.map((r) => (
              <tr
                key={r.requirement_id}
                className="border-b border-border align-top last:border-0 hover:bg-panel-raised"
              >
                <td className="px-4 py-3 font-medium tabular-nums text-text">
                  {r.requirement_code}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-text">{r.requirement_title}</div>
                  <div className="mt-0.5 max-w-md text-xs text-text-muted">{r.explanation}</div>
                </td>
                <td className="px-4 py-3">
                  <VerdictBadge verdict={r.verdict} />
                </td>
                <td className="px-4 py-3 tabular-nums text-text">{r.score.toFixed(0)}</td>
                <td className="px-4 py-3">
                  {r.evidence ? (
                    <>
                      <div className="max-w-xs text-xs text-text">{r.evidence}</div>
                      <div className="mt-0.5 text-xs text-text-faint">
                        {r.source_document}
                        {r.source_page > 0 && ` · p.${r.source_page}`}
                      </div>
                    </>
                  ) : (
                    <span className="text-xs text-text-faint">No evidence found</span>
                  )}
                </td>
                <td className="px-4 py-3 tabular-nums text-text-muted">
                  {Math.round(r.confidence * 100)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-text-muted">
            No requirements with verdict {filter}.
          </p>
        )}
      </Card>
    </div>
  )
}
