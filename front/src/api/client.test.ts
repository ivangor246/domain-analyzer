import { beforeEach, describe, expect, it, vi } from 'vitest'

import { analyzeDomain, cancelAnalysis, createAnalysis, getAnalysis, pollAnalysis } from './client'
import type { AnalysisJob, DomainAnalysis } from './types'

const analysisId = 'a'.repeat(32)

function job(overrides: Partial<AnalysisJob> = {}): AnalysisJob {
  return {
    id: analysisId,
    domain: 'example.com',
    status: 'queued',
    created_at: '2026-08-01T10:00:00Z',
    result: null,
    error: null,
    progress: [],
    ...overrides,
  }
}

function analysis(overrides: Partial<DomainAnalysis> = {}): DomainAnalysis {
  return {
    domain: 'example.com',
    rdap_server: null,
    status: [],
    nameservers: [],
    registrar: null,
    registration_date: null,
    expiration_date: null,
    updated_date: null,
    whois_server: null,
    dns: {
      A: [],
      AAAA: [],
      MX: [],
      TXT: [],
      CNAME: [],
      NS: [],
      SOA: null,
      CAA: [],
      PTR: {},
      propagation: null,
    },
    geoip: {},
    http: null,
    ssl: null,
    ports: null,
    latency: null,
    analysis_errors: [],
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('analyzeDomain', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns the typed analysis response', async () => {
    const response = analysis()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })))

    await expect(analyzeDomain('example.com')).resolves.toEqual(response)
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/domain?d=example.com',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    )
  })

  it('rejects a malformed successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ domain: 'example.com', analysis_errors: [] })))

    await expect(analyzeDomain('example.com')).rejects.toMatchObject({
      name: 'ApiError',
      status: 200,
      code: 'invalid_response',
    })
  })

  it('converts backend errors to ApiError', async () => {
    const response = new Response(
      JSON.stringify({ code: 'invalid_domain', message: 'Invalid domain format' }),
      { status: 400 },
    )
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    await expect(analyzeDomain('invalid')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      code: 'invalid_domain',
      message: 'Invalid domain format',
    })
  })

  it('creates an asynchronous analysis with an idempotency key', async () => {
    const response = job()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(response, 202))
    vi.stubGlobal('fetch', fetchMock)

    await expect(createAnalysis('example.com')).resolves.toEqual(response)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/analyses',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ domain: 'example.com' }),
        headers: expect.objectContaining({
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'Idempotency-Key': expect.stringMatching(/^domain-analyzer-/),
        }),
      }),
    )
  })

  it('rejects a malformed asynchronous job response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          id: analysisId,
          domain: 'example.com',
          status: 'unknown',
          created_at: '2026-08-01T10:00:00Z',
          result: null,
          error: null,
        }),
      ),
    )

    await expect(getAnalysis(analysisId)).rejects.toMatchObject({
      name: 'ApiError',
      status: 200,
      code: 'invalid_response',
    })
  })

  it('rejects malformed check progress in an asynchronous job response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...job({ status: 'running' }),
          progress: [{ check: 'dns', status: 'unknown', duration_ms: null }],
        }),
      ),
    )

    await expect(getAnalysis(analysisId)).rejects.toMatchObject({
      name: 'ApiError',
      status: 200,
      code: 'invalid_response',
    })
  })

  it('gets and cancels an asynchronous analysis', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(job({ status: 'running' })))
      .mockResolvedValueOnce(jsonResponse(job({ status: 'cancelled' })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getAnalysis('job/id')).resolves.toMatchObject({ status: 'running' })
    await expect(cancelAnalysis(analysisId)).resolves.toMatchObject({ status: 'cancelled' })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/analyses/job%2Fid',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/analyses/${analysisId}/cancel`,
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('polls until the analysis reaches a terminal state', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(job({ status: 'queued' })))
      .mockResolvedValueOnce(jsonResponse(job({ status: 'running' })))
      .mockResolvedValueOnce(jsonResponse(job({ status: 'completed' })))
    vi.stubGlobal('fetch', fetchMock)
    const statuses: string[] = []

    await expect(
      pollAnalysis(analysisId, undefined, (currentJob) => statuses.push(currentJob.status), 0),
    ).resolves.toMatchObject({ status: 'completed' })

    expect(statuses).toEqual(['queued', 'running', 'completed'])
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('stops polling when the request is cancelled', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockImplementation(async () => {
      controller.abort()
      return jsonResponse(job({ status: 'running' }))
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(pollAnalysis(analysisId, controller.signal, undefined, 0)).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
