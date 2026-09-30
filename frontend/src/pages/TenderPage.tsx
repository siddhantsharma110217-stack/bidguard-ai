import { Link } from 'react-router-dom'
import { getRequirements } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { useEvaluation } from '../context/EvaluationContext'
import { useApi } from '../hooks/useApi'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { StatTile } from '../components/ui/StatTile'
import { RiskBadge, GateBadge } from '../components/ui/StatusBadges'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconFileText, IconSpinner } from '../components/icons'

function formatTimestamp(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleString()
}

/** One label/value row. Renders nothing when the backend supplied no value,
 *  so the page never shows placeholder or invented data. */
function MetaRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div>
      <dt className="text-xs text-text-faint">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-text">{value}</dd>
    </div>
  )
}

export function TenderPage() {
  const {
    dashboard,
    bids,
    selectedBidId,
    selectBid,
    loading: demoLoading,
    loadDemo,
    error: demoError,
  } = useDemo()
  const tenderId = dashboard?.demo_tender_id ?? null

  const { data, loading, error, reload } = useApi(
    () => getRequirements(tenderId as number),
    [tenderId],
    tenderId != null,
  )

  // Bids for this tender come from the shared context, so the table below and
  // the top-bar bidder picker always agree on which bid is selected.
  const activeBid = bids.find((b) => b.id === selectedBidId) ?? null

  const { results: evaluation, running } = useEvaluation()

  // --- states -------------------------------------------------------------

  if (!demoLoading && tenderId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Tender" description="Tender under evaluation." />
        <EmptyState
          icon={IconFileText}
          title="No tender loaded"
          description="Load the sample GeM tender to review its details, requirements and bids."
          actionLabel="Load Demo"
          onAction={loadDemo}
          actionLoading={demoLoading}
        >
          {demoError && <p className="mt-3 text-sm text-fail">{demoError}</p>}
        </EmptyState>
      </div>
    )
  }

  if (loading || demoLoading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Tender" description="Tender under evaluation." />
        <LoadingState label="Loading tender…" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Tender" description="Tender under evaluation." />
        <ErrorState message={error ?? 'The tender could not be loaded.'} onRetry={reload} />
      </div>
    )
  }

  const { tender } = data
  const uploadedAt = formatTimestamp(tender.uploaded_at)
  const submittedAt = activeBid ? formatTimestamp(activeBid.submitted_at) : null
  const evaluatedAt = activeBid ? formatTimestamp(activeBid.evaluated_at) : null

  const actionClass =
    'inline-flex items-center gap-2 rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised'
  const disabledActionClass =
    'inline-flex items-center gap-2 rounded border border-border px-3 py-1.5 text-xs font-medium text-text-faint cursor-not-allowed'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Tender"
        description={tender.title}
        actions={
          <button
            onClick={loadDemo}
            disabled={demoLoading}
            className="inline-flex items-center gap-2 rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised disabled:opacity-60"
          >
            {demoLoading && <IconSpinner />}
            Reload Demo Data
          </button>
        }
      />

      {/* Tender overview */}
      <Card className="p-5">
        <div className="mb-4 flex items-start justify-between gap-4 border-b border-border pb-4">
          <div>
            <h2 className="text-sm font-semibold text-text">{tender.title}</h2>
            <p className="mt-0.5 text-xs text-text-muted">{tender.reference_no}</p>
          </div>
          <Badge tone={tender.status === 'READY' ? 'pass' : 'neutral'}>{tender.status}</Badge>
        </div>

        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <MetaRow label="Reference Number" value={tender.reference_no} />
          <MetaRow label="Issuing Authority" value={tender.meta.buyer} />
          <MetaRow label="Bid Type" value={tender.meta.bid_type} />
          <MetaRow label="Quantity" value={tender.meta.quantity} />
          <MetaRow label="Source Document" value={tender.filename} />
          <MetaRow label="Pages" value={tender.page_count || null} />
          <MetaRow label="Loaded" value={uploadedAt} />
        </dl>
      </Card>

      {/* Requirement counts */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile
          label="Total Requirements"
          value={String(data.total)}
          hint="Extracted from the tender"
        />
        <StatTile
          label="Mandatory"
          value={String(data.mandatory)}
          hint="Failure blocks responsiveness"
        />
        <StatTile
          label="Desirable"
          value={String(data.desirable)}
          hint="Scored, but non-blocking"
        />
      </div>

      {/* Bidder + evaluation status */}
      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">
            Bids Received {bids.length > 0 && <span className="text-text-faint">({bids.length})</span>}
          </h2>
          {evaluation ? (
            <Badge tone="pass">Evaluated</Badge>
          ) : running ? (
            <Badge tone="neutral">
              <IconSpinner />
              Evaluating…
            </Badge>
          ) : activeBid ? (
            <Badge tone="neutral">Not yet evaluated</Badge>
          ) : null}
        </div>

        {!activeBid ? (
          <p className="text-sm text-text-muted">
            No bids have been submitted against this tender yet.
          </p>
        ) : (
          <>
            <div className="-mx-5 mb-5 overflow-x-auto border-y border-border">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
                    <th className="px-5 py-2.5">Bidder</th>
                    <th className="px-5 py-2.5">Status</th>
                    <th className="px-5 py-2.5">Compliance</th>
                    <th className="px-5 py-2.5">Risk</th>
                    <th className="px-5 py-2.5">Responsiveness</th>
                  </tr>
                </thead>
                <tbody>
                  {bids.map((bid) => {
                    const selected = bid.id === activeBid.id
                    const evaluated = bid.status === 'EVALUATED'
                    return (
                      <tr
                        key={bid.id}
                        onClick={() => selectBid(bid.id)}
                        aria-selected={selected}
                        className={`cursor-pointer border-b border-border last:border-0 ${
                          selected ? 'bg-accent-bg' : 'hover:bg-panel-raised'
                        }`}
                      >
                        <td className="px-5 py-2.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              selectBid(bid.id)
                            }}
                            className={`text-left font-medium ${selected ? 'text-accent' : 'text-text'}`}
                          >
                            {bid.bidder_name}
                          </button>
                        </td>
                        <td className="px-5 py-2.5 text-text-muted">{bid.status}</td>
                        <td className="px-5 py-2.5 tabular-nums text-text">
                          {evaluated ? `${bid.compliance_score}%` : '—'}
                        </td>
                        <td className="px-5 py-2.5">
                          {evaluated ? (
                            <RiskBadge band={bid.risk_band} score={bid.risk_score} />
                          ) : (
                            <span className="text-text-faint">—</span>
                          )}
                        </td>
                        <td className="px-5 py-2.5">
                          {evaluated ? (
                            <GateBadge status={bid.gate_status} />
                          ) : (
                            <span className="text-text-faint">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-text-faint">
              Selected Bid
            </h3>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <MetaRow label="Bidder" value={activeBid.bidder_name} />
              <MetaRow label="Bid Status" value={activeBid.status} />
              <MetaRow label="Submitted" value={submittedAt} />
              <MetaRow label="Evaluated" value={evaluatedAt} />
            </dl>

            {evaluation && (
              <div className="mt-5 flex flex-wrap items-end gap-8 border-t border-border pt-4">
                <div>
                  <div className="text-xs text-text-faint">Overall Compliance</div>
                  <div className="mt-1 text-2xl font-semibold tabular-nums text-text">
                    {evaluation.summary.overall_compliance}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-faint">Risk</div>
                  <div className="mt-1.5">
                    <RiskBadge
                      band={evaluation.summary.risk_band}
                      score={evaluation.summary.risk_score}
                    />
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-faint">Responsiveness</div>
                  <div className="mt-1.5">
                    <GateBadge status={evaluation.summary.gate_status} />
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-faint">Verdicts</div>
                  <div className="mt-1 text-sm tabular-nums text-text">
                    <span className="text-pass">{evaluation.summary.passed} pass</span>
                    {' · '}
                    <span className="text-review">{evaluation.summary.review} review</span>
                    {' · '}
                    <span className="text-fail">{evaluation.summary.failed} fail</span>
                    {' · '}
                    <span className="text-missing">{evaluation.summary.missing} missing</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Contextual navigation */}
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-text">Next Steps</h2>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Link to="/requirements" className={actionClass}>
            View Requirements ({data.total})
          </Link>

          {activeBid ? (
            <Link to="/documents" className={actionClass}>
              View Documents
            </Link>
          ) : (
            <span className={disabledActionClass} aria-disabled="true">
              View Documents
            </span>
          )}

          {activeBid ? (
            <Link to="/evaluation" className={actionClass}>
              {evaluation ? 'Review Evaluation' : 'Go to Evaluation'}
            </Link>
          ) : (
            <span className={disabledActionClass} aria-disabled="true">
              Go to Evaluation
            </span>
          )}

          {evaluation && (
            <>
              <Link to="/compliance" className={actionClass}>
                Compliance Summary
              </Link>
              <Link to="/reports" className={actionClass}>
                Evaluation Report
              </Link>
            </>
          )}
        </div>

        {!activeBid && (
          <p className="mt-3 text-xs text-text-muted">
            Document and evaluation actions become available once a bid is submitted against
            this tender.
          </p>
        )}
      </Card>
    </div>
  )
}
