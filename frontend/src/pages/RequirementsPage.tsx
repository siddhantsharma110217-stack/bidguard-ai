import { useMemo } from 'react'
import { getRequirements } from '../api/client'
import type { EvaluationResult } from '../types'
import { useDemo } from '../context/DemoContext'
import { useEvaluation } from '../context/EvaluationContext'
import { useApi } from '../hooks/useApi'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { VerdictBadge } from '../components/ui/VerdictBadge'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconListChecks, IconSpinner } from '../components/icons'

export function RequirementsPage() {
  const { dashboard, bids, selectedBidId: bidId, loading: demoLoading, loadDemo } = useDemo()
  const tenderId = dashboard?.demo_tender_id ?? null
  const selectedBid = bids.find((b) => b.id === bidId) ?? null

  const {
    data,
    loading,
    error,
    reload,
  } = useApi(() => getRequirements(tenderId as number), [tenderId], tenderId != null)

  // Verdicts come from the shared evaluation context, so this table can never
  // disagree with the Evaluation / Compliance / Reports pages.
  const { results: evaluation, loading: evaluationLoading } = useEvaluation()
  const resultsByCode = useMemo(() => {
    if (!evaluation) return null
    const map: Record<string, EvaluationResult> = {}
    evaluation.results.forEach((res) => {
      map[res.requirement_code] = res
    })
    return map
  }, [evaluation])

  if (!demoLoading && tenderId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Requirements" description="Requirements extracted from the tender." />
        <EmptyState
          icon={IconListChecks}
          title="No tender loaded"
          description="Load the sample tender to see its extracted requirements."
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
        <PageHeader title="Requirements" description="Requirements extracted from the tender." />
        <LoadingState label="Loading requirements…" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Requirements" description="Requirements extracted from the tender." />
        <ErrorState message={error ?? 'Requirements could not be loaded.'} onRetry={reload} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Requirements"
        description={
          selectedBid
            ? `${data.tender.title} — status shown for ${selectedBid.bidder_name}`
            : data.tender.title
        }
      />

      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
            Tender Reference
          </div>
          <div className="mt-2 text-sm font-semibold text-text">{data.tender.reference_no}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
            Total Requirements
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums text-text">{data.total}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
            Mandatory / Desirable
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums text-text">
            {data.mandatory} <span className="text-sm font-normal text-text-faint">/ {data.desirable}</span>
          </div>
        </Card>
      </div>

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Requirement</th>
              <th className="px-4 py-3">Mandatory</th>
              <th className="px-4 py-3">Expected Condition</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.requirements.map((req) => {
              const result = resultsByCode?.[req.code]
              return (
                <tr key={req.id} className="border-b border-border last:border-0 hover:bg-panel-raised">
                  <td className="px-4 py-3 font-medium text-text tabular-nums">{req.code}</td>
                  <td className="px-4 py-3 text-text-muted">{req.category}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{req.title}</div>
                    <div className="mt-0.5 text-xs text-text-muted">{req.description}</div>
                  </td>
                  <td className="px-4 py-3">
                    {req.obligation === 'MANDATORY' ? (
                      <Badge tone="accent">Mandatory</Badge>
                    ) : (
                      <Badge tone="neutral">Desirable</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-muted">{req.expected_condition}</td>
                  <td className="px-4 py-3">
                    {result ? (
                      <VerdictBadge verdict={result.verdict} />
                    ) : (
                      <Badge tone="neutral">Not yet evaluated</Badge>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      {evaluationLoading && bidId != null && (
        <p className="text-xs text-text-faint">
          <IconSpinner className="mr-1 inline-block align-[-2px]" />
          Checking whether this bid has already been evaluated…
        </p>
      )}
    </div>
  )
}
