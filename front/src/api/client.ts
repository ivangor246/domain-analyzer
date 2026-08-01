import type { AnalysisJob, AnalysisJobStatus, DomainAnalysis, ErrorPayload } from './types'
import { isAnalysisJob, isDomainAnalysis, isErrorPayload } from './validators'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: ErrorPayload['details']

  constructor(message: string, status: number, code: string, details?: ErrorPayload['details']) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function analyzeDomain(domain: string, signal?: AbortSignal): Promise<DomainAnalysis> {
  const endpoint = `${API_URL}/api/domain?d=${encodeURIComponent(domain)}`
  return requestJson<DomainAnalysis>(endpoint, {
    headers: { Accept: 'application/json' },
    signal,
  }, isDomainAnalysis)
}

async function requestJson<T>(
  endpoint: string,
  init: RequestInit | undefined,
  validate: (value: unknown) => value is T,
): Promise<T> {
  let response: Response

  try {
    response = await fetch(endpoint, init)
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw error
    }
    throw new Error('The backend could not be reached. Check the API URL and try again.')
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isErrorPayload(body)) {
      throw new ApiError(body.message, response.status, body.code, body.details)
    }
    throw new ApiError('The backend returned an unexpected error.', response.status, 'unknown_error')
  }

  if (!validate(body)) {
    throw new ApiError('The backend returned an invalid response.', response.status, 'invalid_response')
  }

  return body
}

function idempotencyKey() {
  const randomId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `domain-analyzer-${randomId}`
}

export async function createAnalysis(domain: string): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(`${API_URL}/api/analyses`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey(),
    },
    body: JSON.stringify({ domain }),
  }, isAnalysisJob)
}

export async function getAnalysis(analysisId: string, signal?: AbortSignal): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(`${API_URL}/api/analyses/${encodeURIComponent(analysisId)}`, {
    headers: { Accept: 'application/json' },
    signal,
  }, isAnalysisJob)
}

export async function cancelAnalysis(analysisId: string): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(`${API_URL}/api/analyses/${encodeURIComponent(analysisId)}/cancel`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  }, isAnalysisJob)
}

function isTerminalStatus(status: AnalysisJobStatus) {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

function waitForNextPoll(delayMs: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = globalThis.setTimeout(() => {
      signal?.removeEventListener('abort', abort)
      resolve()
    }, delayMs)

    const abort = () => {
      globalThis.clearTimeout(timer)
      reject(new DOMException('The analysis polling was cancelled.', 'AbortError'))
    }

    if (signal?.aborted) {
      abort()
      return
    }
    signal?.addEventListener('abort', abort, { once: true })
  })
}

export async function pollAnalysis(
  analysisId: string,
  signal?: AbortSignal,
  onUpdate?: (job: AnalysisJob) => void,
  intervalMs = 750,
): Promise<AnalysisJob> {
  let job = await getAnalysis(analysisId, signal)
  onUpdate?.(job)

  while (!isTerminalStatus(job.status)) {
    await waitForNextPoll(intervalMs, signal)
    job = await getAnalysis(analysisId, signal)
    onUpdate?.(job)
  }

  return job
}
