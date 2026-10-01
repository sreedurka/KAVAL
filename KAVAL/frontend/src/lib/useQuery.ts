import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

export interface QueryState<T> {
  data: T | null
  error: ApiError | Error | null
  loading: boolean
  /** True while refetching with data already on screen — keeps the old value visible. */
  refreshing: boolean
  reload: () => void
}

/**
 * Minimal fetch-with-state. No cache, no retry: an audit tool that silently
 * serves a stale number is worse than one that shows a spinner.
 */
export function useQuery<T>(fn: () => Promise<T>, deps: unknown[]): QueryState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [nonce, setNonce] = useState(0)
  const seq = useRef(0)
  const hasData = useRef(false)

  const reload = useCallback(() => setNonce((x) => x + 1), [])

  useEffect(() => {
    const id = ++seq.current
    if (hasData.current) setRefreshing(true)
    else setLoading(true)
    fn()
      .then((d) => {
        if (seq.current !== id) return
        setData(d)
        hasData.current = true
        setError(null)
      })
      .catch((e) => {
        if (seq.current !== id) return
        setError(e instanceof Error ? e : new Error(String(e)))
        setData(null)
        hasData.current = false
      })
      .finally(() => {
        if (seq.current !== id) return
        setLoading(false)
        setRefreshing(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, error, loading, refreshing, reload }
}

/** Debounce a rapidly-changing value (the threshold and budget sliders). */
export function useDebounced<T>(value: T, ms = 220): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}
