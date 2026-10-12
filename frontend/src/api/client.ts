import type {
  HealthResponse,
  MetricsResponse,
  OverviewResponse,
  PredictRequest,
  PredictResponse,
  ShotsQuery,
  ShotsResponse,
} from './types'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Turn FastAPI's error body ({detail: string | validation errors[]}) into one readable line. */
function describeError(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.filter((p) => p !== 'body').join('.')
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return `Request failed with status ${status}`
}

const REQUEST_TIMEOUT_MS = 15_000

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    })
  } catch (err) {
    if (timeout.aborted && !signal?.aborted) {
      throw new ApiError(`The FootStat API at ${API_BASE_URL} did not respond within ${REQUEST_TIMEOUT_MS / 1000} seconds.`, null)
    }
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(
      `Can't reach the FootStat API at ${API_BASE_URL}. Make sure the backend is running.`,
      null,
    )
  }

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // Non-JSON body; fall through to the status-based message.
  }
  if (!response.ok) throw new ApiError(describeError(body, response.status), response.status)
  return body as T
}

function queryString(params: object): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>('/api/health', undefined, signal),
  overview: (signal?: AbortSignal) => request<OverviewResponse>('/api/overview', undefined, signal),
  metrics: (signal?: AbortSignal) => request<MetricsResponse>('/api/metrics', undefined, signal),
  shots: (query: ShotsQuery = {}, signal?: AbortSignal) =>
    request<ShotsResponse>(`/api/shots${queryString(query)}`, undefined, signal),
  predict: (body: PredictRequest, signal?: AbortSignal) =>
    request<PredictResponse>(
      '/api/predict',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
      signal,
    ),
}
