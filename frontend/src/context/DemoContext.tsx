import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, getDashboard, loadDemo as loadDemoApi } from '../api/client'
import type { Dashboard } from '../types'

interface DemoContextValue {
  dashboard: Dashboard | null
  loading: boolean
  error: string | null
  /** Loads (or re-fetches) the demo tender + bidder package. */
  loadDemo: () => Promise<void>
  /** Re-reads /api/dashboard without touching the underlying data. */
  refresh: () => Promise<void>
}

const DemoContext = createContext<DemoContextValue | null>(null)

export function DemoProvider({ children }: { children: ReactNode }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await getDashboard()
      setDashboard(result)
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

  return (
    <DemoContext.Provider value={{ dashboard, loading, error, loadDemo, refresh }}>
      {children}
    </DemoContext.Provider>
  )
}

export function useDemo(): DemoContextValue {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo() must be used inside <DemoProvider>')
  return ctx
}
