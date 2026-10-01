import { useState } from 'react'
import { ApiError, listAuditEvents, verifyAuditChain } from '../api/client'
import type { AuditEvent, AuditVerification } from '../types'
import { useApi } from '../hooks/useApi'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { VerdictBadge } from '../components/ui/VerdictBadge'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconLock, IconSpinner } from '../components/icons'

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

function shortHash(hash: string): string {
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`
}

function EventDetail({ event }: { event: AuditEvent }) {
  if (event.event_type === 'VERDICT_OVERRIDE') {
    return (
      <>
        <div className="font-medium text-text">
          {event.requirement_code} — {event.requirement_title}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {event.system_verdict && <VerdictBadge verdict={event.system_verdict} />}
          <span className="text-text-faint">→</span>
          {event.officer_verdict && <VerdictBadge verdict={event.officer_verdict} />}
        </div>
        <p className="mt-1 max-w-md text-xs text-text-muted">{event.reason}</p>
      </>
    )
  }
  return (
    <>
      <div className="font-medium text-text">{event.document_name}</div>
      <div className="mt-0.5 font-mono text-[11px] break-all text-text-faint">
        SHA-256 {event.document_sha256}
      </div>
    </>
  )
}

export function AuditPage() {
  const { data: events, loading, error, reload } = useApi(listAuditEvents, [])
  const [verification, setVerification] = useState<AuditVerification | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  async function handleVerify() {
    setVerifying(true)
    setVerifyError(null)
    try {
      setVerification(await verifyAuditChain())
      // Show the same rows the verification just checked.
      reload()
    } catch (err) {
      setVerification(null)
      setVerifyError(err instanceof ApiError ? err.message : 'Verification failed.')
    } finally {
      setVerifying(false)
    }
  }

  const brokenId = verification?.first_broken?.id ?? null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Audit Log"
        description="Every officer override and document fingerprint, hash-chained so any later edit is detectable."
        actions={
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-60"
          >
            {verifying && <IconSpinner />}
            {verifying ? 'Verifying…' : 'Verify integrity'}
          </button>
        }
      />

      {verifyError && <p className="text-sm text-fail">{verifyError}</p>}

      {verification &&
        (verification.intact ? (
          <div
            role="status"
            className="rounded-md border border-pass/40 bg-pass-bg p-4 text-sm text-pass"
          >
            <div className="font-semibold">Audit chain intact</div>
            <div className="mt-1 text-text-muted">
              All {verification.total_events} events verified at{' '}
              {formatTimestamp(verification.checked_at)}. Head hash{' '}
              <span className="font-mono text-xs">{verification.head_hash}</span>
            </div>
          </div>
        ) : (
          <div role="alert" className="rounded-md border border-fail/40 bg-fail-bg p-4 text-sm text-fail">
            <div className="font-semibold">
              Audit chain broken at event #{verification.first_broken?.id}
            </div>
            <div className="mt-1 text-text-muted">
              {verification.first_broken?.reason} {verification.verified_events} of{' '}
              {verification.total_events} events verified before the break; every event from
              position {verification.first_broken?.position} on cannot be trusted.
            </div>
          </div>
        ))}

      {loading && !events ? (
        <LoadingState label="Loading audit log…" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !events || events.length === 0 ? (
        <EmptyState
          icon={IconLock}
          title="No audit events yet"
          description="Loading bid documents and overriding verdicts on the Evaluation page are recorded here."
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Bidder</th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3">Officer</th>
                <th className="px-4 py-3">Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr
                  key={e.id}
                  className={`border-b border-border align-top last:border-0 ${
                    e.id === brokenId ? 'bg-fail-bg' : ''
                  }`}
                >
                  <td className="px-4 py-3 tabular-nums text-text">{e.id}</td>
                  <td className="px-4 py-3 text-xs whitespace-nowrap text-text-muted">
                    {formatTimestamp(e.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-xs font-medium text-text">
                    {e.event_type === 'VERDICT_OVERRIDE' ? 'Verdict override' : 'Document loaded'}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-muted">{e.bidder_name || '—'}</td>
                  <td className="px-4 py-3">
                    <EventDetail event={e} />
                  </td>
                  <td className="px-4 py-3 text-xs text-text">{e.officer_name || '—'}</td>
                  <td className="px-4 py-3 font-mono text-[11px] whitespace-nowrap text-text-faint">
                    <div title={e.hash}>{shortHash(e.hash)}</div>
                    <div title={e.prev_hash} className="mt-0.5">
                      prev {shortHash(e.prev_hash)}
                    </div>
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
