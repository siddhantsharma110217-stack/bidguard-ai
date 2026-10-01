import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, createOverride, getEvaluationResults, runEvaluation } from '../api/client'
import type { EvaluationResults, OverrideRequest } from '../types'
import { useDemo } from './DemoContext'

/**
 * Single source of truth for the current bid's evaluation result.
 *
 * The Evaluation, Compliance and Reports pages all read from here, so they
 * can never disagree with each other or drift out of sync. Nothing in this
 * provider derives or invents numbers — every figure comes from the backend
 * `/api/evaluations/{bid_id}/results` response.
 */
interface EvaluationContextValue {
  results: EvaluationResults | null
  /** Initial fetch — "have we been evaluated yet?" */
  loading: boolean
  /** Hard failure (network / 5xx). A 404 is not an error: it means "not run yet". */
  error: string | null
  /** An evaluation is currently executing. */
  running: boolean
  runError: string | null
  hasEvaluation: boolean
  bidId: number | null
  run: () => Promise<void>
  /** Records an officer override. Throws ApiError so the form can show it. */
  override: (payload: OverrideRequest) => Promise<void>
  reload: () => void
}

const EvaluationContext = createContext<EvaluationContextValue | null>(null)

export function EvaluationProvider({ children }: { children: ReactNode }) {
  const { dashboard, refresh: refreshDashboard } = useDemo()
  const bidId = dashboard?.demo_bid_id ?? null

  const [results, setResults] = useState<EvaluationResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const reload = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (bidId == null) {
      setResults(null)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getEvaluationResults(bidId)
      .then((r) => {
        if (!cancelled) setResults(r)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setResults(null) // not evaluated yet — a valid state, not a failure
        } else {
          setError(err instanceof ApiError ? err.message : 'Something went wrong.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [bidId, tick])

  const run = useCallback(async () => {
    if (bidId == null) return
    setRunning(true)
    setRunError(null)
    try {
      const r = await runEvaluation(bidId)
      setResults(r)
      // Dashboard tiles (bids evaluated, avg compliance, high-risk) derive from
      // evaluation state, so they must be re-read after a run completes.
      await refreshDashboard()
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'Evaluation failed.')
    } finally {
      setRunning(false)
    }
  }, [bidId, refreshDashboard])

  const override = useCallback(
    async (payload: OverrideRequest) => {
      if (bidId == null) return
      const r = await createOverride(bidId, payload)
      setResults(r)
      // Overrides change the bid's scores, which the dashboard tiles read.
      await refreshDashboard()
    },
    [bidId, refreshDashboard],
  )

  return (
    <EvaluationContext.Provider
      value={{
        results,
        loading,
        error,
        running,
        runError,
        hasEvaluation: results !== null,
        bidId,
        run,
        override,
        reload,
      }}
    >
      {children}
    </EvaluationContext.Provider>
  )
}

export function useEvaluation(): EvaluationContextValue {
  const ctx = useContext(EvaluationContext)
  if (!ctx) throw new Error('useEvaluation() must be used inside <EvaluationProvider>')
  return ctx
}
