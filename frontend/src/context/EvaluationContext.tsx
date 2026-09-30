import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, getEvaluationResults, runEvaluation } from '../api/client'
import type { EvaluationResults } from '../types'
import { useDemo } from './DemoContext'

/**
 * Single source of truth for the selected bid's evaluation result.
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
  reload: () => void
}

const EvaluationContext = createContext<EvaluationContextValue | null>(null)

export function EvaluationProvider({ children }: { children: ReactNode }) {
  const { selectedBidId: bidId, refresh: refreshDashboard } = useDemo()

  const [fetched, setFetched] = useState<EvaluationResults | null>(null)
  // The bid whose results `fetched` reflects (a 404 leaves `fetched` null).
  const [fetchedFor, setFetchedFor] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const reload = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (bidId == null) {
      setFetched(null)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getEvaluationResults(bidId)
      .then((r) => {
        if (!cancelled) setFetched(r)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setFetched(null) // not evaluated yet — a valid state, not a failure
        } else {
          setError(err instanceof ApiError ? err.message : 'Something went wrong.')
        }
      })
      .finally(() => {
        if (cancelled) return
        setFetchedFor(bidId)
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [bidId, tick])

  // Right after the officer switches bidder, `fetched` still holds the
  // previous bid's results until the effect above re-fetches. Never expose
  // one bidder's verdicts under another bidder's name.
  const results = fetched && fetched.bid.id === bidId ? fetched : null
  const stale = bidId != null && fetchedFor !== bidId

  const run = useCallback(async () => {
    if (bidId == null) return
    setRunning(true)
    setRunError(null)
    try {
      const r = await runEvaluation(bidId)
      setFetched(r)
      // Dashboard tiles (bids evaluated, avg compliance, high-risk) derive from
      // evaluation state, so they must be re-read after a run completes.
      await refreshDashboard()
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'Evaluation failed.')
    } finally {
      setRunning(false)
    }
  }, [bidId, refreshDashboard])

  return (
    <EvaluationContext.Provider
      value={{
        results,
        loading: loading || stale,
        error,
        running,
        runError,
        hasEvaluation: results !== null,
        bidId,
        run,
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
