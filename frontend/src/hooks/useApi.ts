import { useCallback, useEffect, useRef, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

interface Completed<T> {
  key: string | null
  data: T | null
  error: string | null
}

/**
 * Run an API call on mount and whenever `key` changes (encode any parameters
 * in it). Stale requests are aborted, so a slow earlier response never
 * overwrites a newer one. Previous data stays visible while reloading.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [attempt, setAttempt] = useState(0)
  const requestKey = `${key}#${attempt}`
  const [completed, setCompleted] = useState<Completed<T>>({ key: null, data: null, error: null })

  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    const controller = new AbortController()
    fetcherRef.current(controller.signal).then(
      (data) => setCompleted({ key: requestKey, data, error: null }),
      (err: unknown) => {
        if (controller.signal.aborted) return
        setCompleted({ key: requestKey, data: null, error: err instanceof Error ? err.message : 'Unexpected error' })
      },
    )
    return () => controller.abort()
  }, [requestKey])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const done = completed.key === requestKey
  return { data: completed.data, error: done ? completed.error : null, loading: !done, reload }
}
