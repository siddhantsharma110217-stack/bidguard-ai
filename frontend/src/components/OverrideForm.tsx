import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../api/client'
import type { EvaluationResult, OverrideRequest, Verdict } from '../types'
import { IconSpinner } from './icons'
import { REASON_CATEGORIES } from '../overrideCategories'
import { useAuth } from '../context/auth'

const MIN_REASON_LENGTH = 15

const VERDICTS: Verdict[] = ['PASS', 'REVIEW', 'FAIL', 'MISSING']

interface OverrideFormProps {
  result: EvaluationResult
  onSubmit: (payload: OverrideRequest) => Promise<void>
  onCancel: () => void
}

/** Officer override for one requirement. Mirrors the backend's validation so
 *  the officer sees problems before submitting; the backend still enforces it. */
export function OverrideForm({ result, onSubmit, onCancel }: OverrideFormProps) {
  const { user } = useAuth()
  const [verdict, setVerdict] = useState<Verdict>(
    VERDICTS.find((v) => v !== result.verdict) ?? 'PASS',
  )
  const [category, setCategory] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reasonLength = reason.trim().length
  const reasonOk = reasonLength >= MIN_REASON_LENGTH
  const categoryOk = category !== ''
  const changed = verdict !== result.verdict
  const canSubmit = categoryOk && reasonOk && changed && !submitting
  const placeholder =
    REASON_CATEGORIES.find((c) => c.code === category)?.placeholder ??
    'Choose a reason category first'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({
        requirement_id: result.requirement_id,
        verdict,
        reason_category: category,
        reason: reason.trim(),
      })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The override could not be saved.')
      setSubmitting(false)
    }
  }

  const inputClass =
    'w-full rounded border border-border-strong bg-panel px-2.5 py-1.5 text-sm text-text focus:border-accent focus:outline-none'

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 text-sm">
      <div className="text-xs text-text-muted">
        System verdict: <span className="font-medium text-text">{result.system_verdict}</span>
        {result.overridden && (
          <>
            {' '}
            · current officer verdict:{' '}
            <span className="font-medium text-text">{result.verdict}</span>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[10rem_1fr]">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-muted">New verdict</span>
          <select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value as Verdict)}
            className={inputClass}
          >
            {VERDICTS.map((v) => (
              <option key={v} value={v} disabled={v === result.verdict}>
                {v}
                {v === result.system_verdict && result.overridden ? ' (restore system)' : ''}
              </option>
            ))}
          </select>
        </label>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-muted">Officer</span>
          {/* Read-only: the backend records the logged-in officer. */}
          <div className="rounded border border-border bg-panel-raised px-2.5 py-1.5 text-sm text-text">
            {user ? `${user.full_name} (${user.designation})` : '—'}
          </div>
        </div>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-text-muted">Reason category</span>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          required
          className={`${inputClass} sm:max-w-sm`}
        >
          <option value="" disabled>
            Select a reason category…
          </option>
          {REASON_CATEGORIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
        {!categoryOk && <span className="text-xs text-review">A reason category is required</span>}
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-text-muted">
          Details and reference (letter no., document and page, meeting ref)
        </span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder={placeholder}
          className={inputClass}
        />
        <span className={`text-xs ${reasonOk ? 'text-text-faint' : 'text-review'}`}>
          {reasonOk
            ? `${reasonLength} characters`
            : `At least ${MIN_REASON_LENGTH} characters required (${reasonLength}/${MIN_REASON_LENGTH})`}
        </span>
      </label>

      {error && <p className="text-xs text-fail">{error}</p>}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={!canSubmit}
          className="inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-50"
        >
          {submitting && <IconSpinner />}
          {submitting ? 'Saving…' : 'Record override'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised"
        >
          Cancel
        </button>
        <span className="text-xs text-text-faint">
          The override is permanently recorded in the audit log.
        </span>
      </div>
    </form>
  )
}
