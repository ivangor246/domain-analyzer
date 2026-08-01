import { beforeEach, describe, expect, it, vi } from 'vitest'

import { analyzeDomain, ApiError } from './client'

describe('analyzeDomain', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns the typed analysis response', async () => {
    const response = { domain: 'example.com', analysis_errors: [] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })))

    await expect(analyzeDomain('example.com')).resolves.toEqual(response)
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/domain?d=example.com',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    )
  })

  it('converts backend errors to ApiError', async () => {
    const response = new Response(
      JSON.stringify({ code: 'invalid_domain', message: 'Invalid domain format' }),
      { status: 400 },
    )
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    await expect(analyzeDomain('invalid')).rejects.toMatchObject<ApiError>({
      name: 'ApiError',
      status: 400,
      code: 'invalid_domain',
      message: 'Invalid domain format',
    })
  })
})
