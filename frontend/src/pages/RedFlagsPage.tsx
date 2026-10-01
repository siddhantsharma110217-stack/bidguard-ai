import { getRedFlags } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { useApi } from '../hooks/useApi'
import type { RedFlag, RedFlagCategory } from '../types'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconFlag, IconShieldCheck } from '../components/icons'

const TITLE = 'Red Flags'

const CATEGORY_LABEL: Record<RedFlagCategory, string> = {
  POSSIBLE_COLLUSION: 'Possible collusion',
  INCONSISTENT_TREATMENT: 'Inconsistent treatment',
}

function Disclaimer({ text }: { text: string }) {
  return (
    <span className="text-xs font-semibold text-review">{text}</span>
  )
}

function FlagCard({ flag, disclaimer }: { flag: RedFlag; disclaimer: string }) {
  return (
    <Card className="border-review/40 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={flag.category === 'POSSIBLE_COLLUSION' ? 'fail' : 'review'}>
          {CATEGORY_LABEL[flag.category]}
        </Badge>
        <h3 className="text-sm font-semibold text-text">{flag.title}</h3>
        {flag.similarity != null && (
          <span className="text-xs tabular-nums text-text-muted">{flag.similarity}% similar</span>
        )}
      </div>
      <div className="mt-1">
        <Disclaimer text={disclaimer} />
      </div>

      <p className="mt-2 text-sm text-text-muted">{flag.summary}</p>

      <div className="mt-3 text-xs text-text-faint">
        Bidders involved:{' '}
        <span className="font-medium text-text">
          {flag.bidders.map((b) => b.bidder_name).join(', ')}
        </span>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[640px] table-fixed text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
              <th className="w-1/4 py-2 pr-4">Bidder</th>
              <th className="py-2 pr-4">Evidence</th>
              <th className="w-1/4 py-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {flag.evidence.map((e, i) => (
              <tr key={`${e.bid_id}-${i}`} className="border-b border-border align-top last:border-0">
                <td className="py-2 pr-4 font-medium text-text">{e.bidder_name}</td>
                <td className="py-2 pr-4">
                  <div className="text-xs font-medium text-text">{e.label}</div>
                  {e.value && <div className="mt-0.5 max-w-xl text-xs text-text-muted">{e.value}</div>}
                  {e.detail && <div className="mt-0.5 text-xs text-text-faint">{e.detail}</div>}
                </td>
                <td className="py-2 text-xs text-text-faint">
                  {e.source_document || '—'}
                  {e.source_page > 0 && `, page ${e.source_page}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function RedFlagsPage() {
  const { dashboard, loading: demoLoading, loadDemo } = useDemo()
  const tenderId = dashboard?.demo_tender_id ?? null

  const { data, loading, error, reload } = useApi(
    () => getRedFlags(tenderId as number),
    [tenderId],
    tenderId != null,
  )

  if (!demoLoading && tenderId == null) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title={TITLE} />
        <EmptyState
          icon={IconFlag}
          title="No tender loaded"
          description="Load the sample tender and bidder packages to compare bidders."
          actionLabel="Load Demo"
          onAction={loadDemo}
          actionLoading={demoLoading}
        />
      </div>
    )
  }

  if (demoLoading || (loading && !data)) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title={TITLE} />
        <LoadingState label="Comparing bidders…" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title={TITLE} />
        <ErrorState message={error ?? 'Could not load red flags.'} onRetry={reload} />
      </div>
    )
  }

  const unevaluated = data.bidders.filter((b) => !b.evaluated)
  const collusion = data.flags.filter((f) => f.category === 'POSSIBLE_COLLUSION')
  const inconsistent = data.flags.filter((f) => f.category === 'INCONSISTENT_TREATMENT')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={TITLE}
        description={`${data.tender.title} — comparing ${data.bidders.length} bidders`}
        actions={
          <button
            onClick={reload}
            disabled={loading}
            className="rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised disabled:opacity-60"
          >
            {loading ? 'Re-checking…' : 'Re-check'}
          </button>
        }
      />

      <Card className="p-4 text-sm text-text-muted">
        <p>
          Flags shared phone numbers, emails, registered addresses and bank accounts between
          different bidders, documents of the same type whose text is more than{' '}
          {data.similarity_threshold}% similar (documents shorter than{' '}
          {data.min_similarity_text_length} characters, such as standard forms, are skipped), and
          requirements where bidders failing the same rule received different final decisions.
        </p>
        <p className="mt-2">
          Each item is a <Disclaimer text={data.disclaimer} />. It tells the officer where to look;
          it does not establish that anything improper happened.
        </p>
        {unevaluated.length > 0 && (
          <p className="mt-2 text-xs text-text-faint">
            Not yet evaluated, so excluded from the inconsistent-treatment check:{' '}
            {unevaluated.map((b) => b.bidder_name).join(', ')}.
          </p>
        )}
      </Card>

      {data.total_flags === 0 ? (
        <Card className="flex flex-col items-center gap-2 border-pass/40 bg-pass-bg px-6 py-12 text-center">
          <IconShieldCheck width={28} height={28} className="text-pass" />
          <div className="text-base font-semibold text-pass">No red flags</div>
          <p className="max-w-md text-sm text-text-muted">
            None of the {data.bidders.length} bidders share contact details or near-identical
            documents, and every shared rule failure received the same final decision.
          </p>
        </Card>
      ) : (
        <>
          {[
            { label: 'Possible collusion', flags: collusion },
            { label: 'Inconsistent treatment', flags: inconsistent },
          ].map(
            (group) =>
              group.flags.length > 0 && (
                <section key={group.label} className="flex flex-col gap-3">
                  <h2 className="text-sm font-semibold text-text">
                    {group.label} ({group.flags.length})
                  </h2>
                  {group.flags.map((f, i) => (
                    <FlagCard key={`${f.kind}-${f.title}-${i}`} flag={f} disclaimer={data.disclaimer} />
                  ))}
                </section>
              ),
          )}
        </>
      )}
    </div>
  )
}
