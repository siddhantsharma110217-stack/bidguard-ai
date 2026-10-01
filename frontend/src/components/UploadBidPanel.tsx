import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { ApiError, getHealth, uploadBid } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { useApi } from '../hooks/useApi'
import { formatBytes } from '../extraction'
import { Card } from './ui/Card'
import { IconSpinner } from './icons'

const DEFAULT_LIMIT_MB = 10

/** Problems with the chosen files, checked before anything is sent. The
 *  backend repeats every check; this only gives faster feedback. */
function fileProblems(files: File[], limitMb: number): string[] {
  const problems: string[] = []
  for (const f of files) {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      problems.push(`'${f.name}' is not a PDF. Only PDF files (.pdf) are accepted.`)
    } else if (f.size > limitMb * 1024 * 1024) {
      problems.push(`'${f.name}' is ${formatBytes(f.size)}; the limit is ${limitMb} MB per file.`)
    } else if (f.size === 0) {
      problems.push(`'${f.name}' is empty.`)
    }
  }
  return problems
}

export function UploadBidPanel({ onClose }: { onClose: () => void }) {
  const { dashboard, refresh, selectBid } = useDemo()
  const tenderId = dashboard?.demo_tender_id ?? null
  const { data: health } = useApi(getHealth, [])
  const limitMb = health?.max_upload_mb ?? DEFAULT_LIMIT_MB

  const [name, setName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const problems = fileProblems(files, limitMb)
  const canSubmit =
    tenderId != null && name.trim() !== '' && files.length > 0 && problems.length === 0 && !submitting

  function onFiles(e: ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(e.target.files ?? []))
    setError(null)
    setDone(null)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit || tenderId == null) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await uploadBid(tenderId, name.trim(), files)
      await refresh()
      selectBid(result.bid.id)
      setDone(
        `Bid from ${result.bid.bidder_name} uploaded (${result.documents.length} file${
          result.documents.length === 1 ? '' : 's'
        }, ${result.extraction_label}). It is now selected; run the evaluation from the Evaluation page.`,
      )
      setName('')
      setFiles([])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The upload failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const inputClass =
    'w-full rounded border border-border-strong bg-panel px-2.5 py-1.5 text-sm text-text focus:border-accent focus:outline-none'

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-text">Upload a bid</h2>
          <p className="mt-0.5 text-xs text-text-muted">
            Creates a new bidder for this tender. PDF only, up to {limitMb} MB per file. Text is read
            page by page; scanned pages without a text layer are flagged (OCR is not available).
          </p>
        </div>
        <span className="shrink-0 rounded border border-border px-2 py-1 text-xs text-text-muted">
          {health?.extraction_label ?? 'Checking extraction mode…'}
        </span>
      </div>

      <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-muted">Bidder company name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Northwind Edutech Systems Pvt. Ltd."
            className={`${inputClass} sm:max-w-md`}
            maxLength={120}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-muted">Bid documents (PDF)</span>
          <input
            type="file"
            accept=".pdf,application/pdf"
            multiple
            onChange={onFiles}
            className="text-sm text-text file:mr-3 file:rounded file:border file:border-border-strong file:bg-panel-raised file:px-3 file:py-1.5 file:text-xs file:text-text"
          />
        </label>

        {files.length > 0 && (
          <ul className="text-xs text-text-muted">
            {files.map((f) => (
              <li key={`${f.name}-${f.size}`}>
                {f.name} · {formatBytes(f.size)}
              </li>
            ))}
          </ul>
        )}
        {problems.map((p) => (
          <p key={p} className="text-xs text-fail">
            {p}
          </p>
        ))}
        {error && <p className="text-xs text-fail">{error}</p>}
        {done && <p className="text-xs text-pass">{done}</p>}

        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-50"
          >
            {submitting && <IconSpinner />}
            {submitting ? 'Uploading and reading…' : 'Upload bid'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised"
          >
            Close
          </button>
        </div>
      </form>
    </Card>
  )
}
