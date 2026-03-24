import { useState, useEffect } from 'react'

/**
 * Generic data-fetching hook.
 * Pass fetchFn=null to skip fetching (e.g. when a required ID is not yet selected).
 * Cancels in-flight requests on dep change / unmount to prevent stale state.
 */
export function useApi(fetchFn, deps) {
  const [state, setState] = useState({ data: null, loading: !!fetchFn, error: null })

  useEffect(() => {
    if (!fetchFn) {
      setState({ data: null, loading: false, error: null })
      return
    }
    let cancelled = false
    setState({ data: null, loading: true, error: null })
    fetchFn()
      .then(data => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch(err => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message || 'Request failed' })
      })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
