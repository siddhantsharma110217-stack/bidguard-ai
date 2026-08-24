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
import { IconActivity, IconSpinner } from '../components/icons'

export function EvaluationPage() {
  const { loading: demoLoading, loadDemo } = useDemo()
  const { results, loading, error, running, runError, bidId, run, reload } = useEvaluation()

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
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
                <th className="px-4 py-3">Requirement</th>
                <th className="px-4 py-3">Verdict</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Evidence</th>
                <th className="px-4 py-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((r) => (
                <tr
                  key={r.requirement_id}
                  className="border-b border-border align-top last:border-0 hover:bg-panel-raised"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">
                      {r.requirement_code} — {r.requirement_title}
                    </div>
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
                        <div className="mt-0.5 text-xs text-text-faint">{r.source_document}</div>
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
        </Card>
      )}
    </div>
  )
}
