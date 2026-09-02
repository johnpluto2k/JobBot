import { useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/** Run an async fetcher on mount; re-run when `deps` change. */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null })

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    fetcher()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      // Keep whatever data is already on screen when a refetch fails. This used
      // to null it out, so one flaky request after a mutation - marking a company
      // checked, dragging an offer weight slider - replaced a fully populated
      // table the user was reading with a bare error card.
      .catch((err) => alive && setState((s) => ({
        data: s.data, loading: false, error: String(err.message ?? err),
      })))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
