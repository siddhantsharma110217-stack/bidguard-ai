import { Fragment, useState } from 'react'
import { getBidDocuments } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { useEvaluation } from '../context/EvaluationContext'
import { useApi } from '../hooks/useApi'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { VerdictBadge } from '../components/ui/VerdictBadge'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { OverrideForm } from '../components/OverrideForm'
import { EvidenceSource } from '../components/EvidenceSource'
import { VerificationBadge } from '../components/VerificationBadge'
import { VerificationPanel } from '../components/VerificationPanel'
import { TRUST_HELP } from '../verification'
import { useAuth } from '../context/auth'
import { categoryLabel } from '../overrideCategories'
import { IconActivity, IconSpinner } from '../components/icons'

export function EvaluationPage() {
  const { loading: demoLoading, loadDemo } = useDemo()
  const { results, loading, error, running, runError, bidId, run, override, reload } =
    useEvaluation()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [whyId, setWhyId] = useState<number | null>(null)
  // Reviewers see every override but cannot make one (the API would 403).
  const { isOfficer } = useAuth()

  // Tender / bidder names for the pre-evaluation card. Read from the API so
  // this panel describes whatever bid is actually loaded.
  const { data: context } = useApi(
    () => getBidDocuments(bidId as number),
    [bidId],
    bidId != null,
  )

  if (!demoLoading && bidId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Bid Compliance Evaluation" />
        <EmptyState
          icon={IconActivity}
          title="No bid loaded"
          description="Load the sample tender and bidder package before running an evaluation."
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
        <PageHeader title="Bid Compliance Evaluation" />
        <LoadingState label="Checking evaluation status…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Bid Compliance Evaluation" />
        <ErrorState message={error} onRetry={reload} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Bid Compliance Evaluation"
        description={results ? `${results.tender.title} — ${results.bid.bidder_name}` : undefined}
        actions={
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-60"
          >
            {running && <IconSpinner />}
            {running
              ? 'Evaluating…'
              : results
                ? 'Re-run Compliance Evaluation'
                : 'Run Compliance Evaluation'}
          </button>
        }
      />

      {!results && !running && (
        <Card className="p-5">
          <div className="text-sm text-text-muted">
            <div>
              Tender:{' '}
              <span className="font-medium text-text">{context?.tender.title ?? '—'}</span>
            </div>
            <div className="mt-1">
              Bidder:{' '}
              <span className="font-medium text-text">{context?.bid.bidder_name ?? '—'}</span>
            </div>
            <div className="mt-1">
              Documents submitted:{' '}
              <span className="font-medium text-text">{context?.total ?? '—'}</span>
            </div>
          </div>
          <p className="mt-4 text-sm text-text-muted">
            No evaluation has been run for this bid yet. Click{' '}
            <span className="font-medium text-text">Run Compliance Evaluation</span> to compare
            every requirement against the submitted document package.
          </p>
        </Card>
      )}

      {runError && <p className="text-sm text-fail">{runError}</p>}

      {running && <LoadingState label="Evaluating requirements against submitted documents…" />}

      {results && !running && (
        <>
          <p className="text-xs text-text-faint">{TRUST_HELP}</p>
          {/* Fixed columns that fit a 1366px screen without horizontal
              scrolling; long text wraps and the action buttons stay in view. */}
          <Card>
            <table className="w-full table-fixed text-sm">
              <colgroup>
                <col className="w-[31%]" />
                <col className="w-[25%]" />
                <col />
                <col className="w-[7.5rem]" />
              </colgroup>
              <thead>
                <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
                  <th className="px-3 py-3">Requirement</th>
                  <th className="px-3 py-3">Verdict</th>
                  <th className="px-3 py-3">Evidence</th>
                  <th className="px-3 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {results.results.map((r) => {
                  const expanded = editingId === r.requirement_id
                  const showWhy = whyId === r.requirement_id
                  return (
                    <Fragment key={r.requirement_id}>
                      <tr
                        className={`border-b border-border align-top hover:bg-panel-raised ${
                          expanded || showWhy ? 'bg-panel-raised' : ''
                        }`}
                      >
                        <td className="px-3 py-3">
                          <div className="font-medium break-words text-text">
                            {r.requirement_code} — {r.requirement_title}
                          </div>
                          <div className="mt-0.5 text-xs break-words text-text-muted">
                            {r.explanation}
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          {r.verification_required ? (
                            <div className="flex flex-col items-start gap-1.5">
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="w-[4.75rem] text-[11px] text-text-faint">
                                  Compliance
                                </span>
                                <VerdictBadge verdict={r.verdict} />
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="w-[4.75rem] text-[11px] text-text-faint">
                                  Verification
                                </span>
                                <VerificationBadge status={r.verification_status} />
                              </div>
                            </div>
                          ) : (
                            <VerdictBadge verdict={r.verdict} />
                          )}
                          <div className="mt-1.5 text-[11px] tabular-nums text-text-faint">
                            Score {r.score.toFixed(0)} · Confidence {Math.round(r.confidence * 100)}%
                          </div>
                          {r.overridden && (
                            <div className="mt-1.5 rounded border border-border bg-panel px-2 py-1.5 text-xs break-words text-text-muted">
                              <div className="text-[11px] text-text-faint">
                                Overridden · system verdict {r.system_verdict}
                              </div>
                              <div className="font-medium text-text">
                                {categoryLabel(r.override_category)}
                              </div>
                              <span className="font-medium text-text">{r.officer_name}</span>:{' '}
                              {r.override_reason}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          {r.evidence ? (
                            <>
                              <div className="text-xs break-words text-text">{r.evidence}</div>
                              <div className="mt-0.5 text-xs break-words text-text-faint">
                                {r.source_document}
                                {r.source_page > 0 && ` · p.${r.source_page}`}
                              </div>
                              <EvidenceSource result={r} />
                            </>
                          ) : (
                            <span className="text-xs text-text-faint">No evidence found</span>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-col items-stretch gap-1.5">
                            {isOfficer ? (
                              <button
                                onClick={() => setEditingId(expanded ? null : r.requirement_id)}
                                className="rounded border border-border-strong px-2 py-1 text-xs font-medium text-text hover:bg-panel"
                              >
                                {r.overridden ? 'Change' : 'Override'}
                              </button>
                            ) : (
                              <span className="text-xs text-text-faint">View only</span>
                            )}
                            {r.verification_required &&
                              r.verification_status !== 'NOT_APPLICABLE' && (
                                <button
                                  onClick={() => setWhyId(showWhy ? null : r.requirement_id)}
                                  aria-expanded={showWhy}
                                  className="rounded border border-border-strong px-2 py-1 text-xs font-medium text-text hover:bg-panel"
                                >
                                  {showWhy ? 'Hide' : 'Why?'}
                                </button>
                              )}
                          </div>
                        </td>
                      </tr>
                      {showWhy && (
                        <tr className="border-b border-border bg-panel-raised">
                          <td colSpan={4} className="px-3 pb-4 pt-1">
                            <VerificationPanel result={r} />
                          </td>
                        </tr>
                      )}
                      {isOfficer && expanded && (
                        <tr className="border-b border-border bg-panel-raised">
                          <td colSpan={4} className="px-3 pb-4 pt-1">
                            <OverrideForm
                              result={r}
                              onSubmit={async (payload) => {
                                await override(payload)
                                setEditingId(null)
                              }}
                              onCancel={() => setEditingId(null)}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  )
}
