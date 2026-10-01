import type { EvaluationResult, FieldCheck } from '../types'
import { formatCheckedAt, TRUST_HELP } from '../verification'
import { VerificationBadge } from './VerificationBadge'

/** "Why?" panel: submitted values next to the issuer's record. */
export function VerificationPanel({ result }: { result: EvaluationResult }) {
  const d = result.verification_details ?? {}
  const rows: (FieldCheck & { ok: boolean })[] = [
    ...(d.mismatched ?? []).map((f) => ({ ...f, ok: false })),
    ...(d.matched ?? []).map((f) => ({ ...f, ok: true })),
  ]
  const noRecord = result.verification_status === 'UNVERIFIED' && !d.issuer_record

  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-text-muted">Verification</span>
        <VerificationBadge status={result.verification_status} />
      </div>
      <p className="text-text">{result.verification_reason}</p>

      {noRecord ? (
        <p className="rounded border border-review/40 bg-review-bg px-3 py-2 text-xs text-review">
          No issuer record available
          {d.submitted?.certificate_number
            ? ` for certificate number ${d.submitted.certificate_number}.`
            : '.'}
        </p>
      ) : rows.length > 0 ? (
        <table className="w-full table-fixed text-xs">
          <thead>
            <tr className="border-b border-border text-left uppercase tracking-wide text-text-faint">
              <th className="w-1/4 py-1.5 pr-3">Field</th>
              <th className="py-1.5 pr-3">Submitted value</th>
              <th className="py-1.5">Issuer record</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr
                key={f.field}
                className={`border-b border-border last:border-0 ${f.ok ? '' : 'bg-fail-bg'}`}
              >
                <td className="py-1.5 pr-3 font-medium text-text">
                  {f.label}
                  {!f.ok && <span className="ml-1 text-fail">(mismatch)</span>}
                </td>
                <td className={`py-1.5 pr-3 break-words ${f.ok ? 'text-text' : 'font-semibold text-fail'}`}>
                  {f.submitted || '—'}
                </td>
                <td className={`py-1.5 break-words ${f.ok ? 'text-text' : 'font-semibold text-fail'}`}>
                  {f.issuer || '—'}
                </td>
              </tr>
            ))}
            {d.issuer_record?.valid_until && (
              <tr>
                <td className="py-1.5 pr-3 font-medium text-text">Valid until</td>
                <td className="py-1.5 pr-3 text-text-faint">—</td>
                <td className="py-1.5 text-text">{d.issuer_record.valid_until}</td>
              </tr>
            )}
          </tbody>
        </table>
      ) : null}

      <div className="text-xs text-text-faint">
        {d.submitted && (
          <div>
            Submitted: {d.submitted.document_name}
            {d.submitted.page > 0 && `, page ${d.submitted.page}`}. Holder from{' '}
            {d.submitted.holder_source}.
          </div>
        )}
        <div>
          Source: {result.verification_source || '—'} · Checked{' '}
          {formatCheckedAt(result.verification_checked_at)}
        </div>
        <div className="mt-1">{TRUST_HELP}</div>
      </div>
    </div>
  )
}
