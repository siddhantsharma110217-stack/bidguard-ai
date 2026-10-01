import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, getDashboard, listBids, loadDemo as loadDemoApi } from '../api/client'
import type { Bid, Dashboard } from '../types'

interface DemoContextValue {
  dashboard: Dashboard | null
  /** Every bid on the demo tender, in submission order. */
  bids: Bid[]
  /** The bid the officer is currently reviewing. Every bid-scoped page
   *  (Documents, Evaluation, Compliance, Reports) follows this id. */
  selectedBidId: number | null
  selectBid: (bidId: number) => void
  loading: boolean
  error: string | null
  /** Loads (or re-fetches) the demo tender + bidder packages. */
  loadDemo: () => Promise<void>
  /** Re-reads /api/dashboard and the tender's bids without touching the underlying data. */
  refresh: () => Promise<void>
}

const DemoContext = createContext<DemoContextValue | null>(null)

// The officer's bidder choice survives page reloads in this browser only.
// Storage can be unavailable (private mode, blocked site data): never fail on it.
const SELECTED_BID_KEY = 'bidguard.selectedBidId'

function readStoredBidId(): number | null {
  try {
    const raw = localStorage.getItem(SELECTED_BID_KEY)
    return raw == null ? null : Number(raw) || null
  } catch {
    return null
  }
}

function storeBidId(bidId: number): void {
  try {
    localStorage.setItem(SELECTED_BID_KEY, String(bidId))
  } catch {
    // selection still works for this session
  }
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [bids, setBids] = useState<Bid[]>([])
  const [chosenBidId, setChosenBidId] = useState<number | null>(readStoredBidId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await getDashboard()
      const tenderId = result.demo_tender_id
      // Filter client-side too: an older backend ignores `?tender_id=`.
      const tenderBids =
        tenderId != null
          ? (await listBids(tenderId)).filter((b) => b.tender_id === tenderId)
          : []
      setDashboard(result)
      setBids(tenderBids)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the backend.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDemo = useCallback(async () => {
    setLoading(true)
    try {
      await loadDemoApi()
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the demo dataset.')
      setLoading(false)
    }
  }, [refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  const selectBid = useCallback((bidId: number) => {
    setChosenBidId(bidId)
    storeBidId(bidId)
  }, [])

  // Fall back to the primary demo bid until the officer picks one, or if the
  // chosen bid no longer exists (e.g. after the demo was reset).
  const selectedBidId =
    chosenBidId != null && bids.some((b) => b.id === chosenBidId)
      ? chosenBidId
      : (dashboard?.demo_bid_id ?? null)

  return (
    <DemoContext.Provider
      value={{
        dashboard,
        bids,
        selectedBidId,
        selectBid,
        loading,
        error,
        loadDemo,
        refresh,
      }}
    >
      {children}
    </DemoContext.Provider>
  )
}

export function useDemo(): DemoContextValue {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo() must be used inside <DemoProvider>')
  return ctx
}
