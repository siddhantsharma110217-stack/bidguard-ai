import { useState } from 'react'
import { ApiError, reverifyDocument } from '../api/client'
import type { BidDocument, FileCheckStatus } from '../types'
import { formatCheckedAt } from '../verification'
import { VerificationBadge } from './VerificationBadge'
import { Badge } from './ui/Badge'
import { IconSpinner } from './icons'

const FILE_LABEL: Record<FileCheckStatus, string> = {
  UNCHANGED: 'Unchanged since upload',
  CHANGED: 'FILE CHANGED SINCE UPLOAD',
  FILE_MISSING: 'Stored file is missing',
}

/** SHA-256, issuer verification, signature presence and the file re-check
 *  for one document. None of these, alone, proves a document is genuine. */
export function DocumentTrustCell({
  bidId,
  doc,
  canReverify,
}: {
  bidId: number
  doc: BidDocument
  canReverify: boolean
}) {
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<{ status: FileCheckStatus; at: string | null } | null>(
    doc.last_reverify_status ? { status: doc.last_reverify_status, at: doc.last_reverified_at } : null,
  )

  async function reverify() {
    setChecking(true)
    setError(null)
    try {
      const result = await reverifyDocument(bidId, doc.id)
      setLast({ status: result.status, at: result.checked_at })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The file could not be re-verified.')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex flex-col gap-1.5 text-xs">
      <div className="font-mono text-[11px] break-all text-text-faint" title={doc.sha256}>
        SHA-256 {doc.sha256 ? `${doc.sha256.slice(0, 16)}…` : 'not recorded'}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-text-faint">Verification</span>
        {doc.verification_status ? (
          <VerificationBadge status={doc.verification_status} />
        ) : (
          <span className="text-text-faint">not checked</span>
        )}
      </div>
      {doc.has_signature_field !== null && (
        <div className="text-text-muted">
          Digitally signed: <span className="font-medium text-text">{doc.has_signature_field ? 'yes' : 'no'}</span>
          {doc.has_signature_field && (
            <div className="text-[11px] text-text-faint">
              Signature validity and signer not verified in this prototype
            </div>
          )}
        </div>
      )}
      {last && (
        <div>
          <Badge tone={last.status === 'UNCHANGED' ? 'pass' : 'fail'}>{FILE_LABEL[last.status]}</Badge>
          <div className="mt-0.5 text-[11px] text-text-faint">Checked {formatCheckedAt(last.at)}</div>
        </div>
      )}
      {error && <div className="text-fail">{error}</div>}
      {doc.reverifiable && canReverify && (
        <button
          onClick={reverify}
          disabled={checking}
          className="inline-flex w-fit items-center gap-1.5 rounded border border-border-strong px-2 py-1 text-xs font-medium text-text hover:bg-panel-raised disabled:opacity-60"
        >
          {checking && <IconSpinner />}
          {checking ? 'Re-verifying…' : 'Re-verify file'}
        </button>
      )}
    </div>
  )
}
