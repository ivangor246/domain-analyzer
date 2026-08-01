import type { DomainAnalysis, ErrorPayload } from './types'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

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

function isErrorPayload(value: unknown): value is ErrorPayload {
  if (!value || typeof value !== 'object') {
    return false
  }

  const payload = value as Partial<ErrorPayload>
  return typeof payload.code === 'string' && typeof payload.message === 'string'
}

export async function analyzeDomain(domain: string, signal?: AbortSignal): Promise<DomainAnalysis> {
  const endpoint = `${API_URL}/api/domain?d=${encodeURIComponent(domain)}`
  let response: Response

  try {
    response = await fetch(endpoint, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
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

  return body as DomainAnalysis
}
