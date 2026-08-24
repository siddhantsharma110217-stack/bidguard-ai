import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

interface UseApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

interface UseApiResult<T> extends UseApiState<T> {
  reload: () => void
}

/**
 * Runs `fetcher` on mount and whenever `deps` change, tracking loading/error
 * state. Pass `enabled: false` to skip fetching (e.g. until a required id is
 * known). Errors are always rendered as the backend's own message, never a
 * raw exception.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
  enabled = true,
): UseApiResult<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: enabled,
    error: null,
  })
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const reload = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, loading: false, error: null })
      return
    }

    let cancelled = false
    setState((prev) => ({ ...prev, loading: true, error: null }))

    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof ApiError ? err.message : 'Something went wrong.'
        setState({ data: null, loading: false, error: message })
      })

    return () => {
      cancelled = true
    }
    // `deps` intentionally drives refetching directly; `fetcher` itself is
    // read from a ref so callers can pass a fresh closure each render.
  }, [enabled, tick, ...deps])

  return { ...state, reload }
}
