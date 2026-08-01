import { describe, expect, it } from 'vitest'

import type { DomainAnalysis, HTTPProbeResult } from '../api/types'
import { getSecuritySummary } from './security'

function probe(overrides: Partial<HTTPProbeResult> = {}): HTTPProbeResult {
  return {
    reachable: false,
    status_code: null,
    final_url: null,
    redirect_chain: [],
    response_time_ms: null,
    server: null,
    x_powered_by: null,
    via: null,
    content_type: null,
    cache_control: null,
    content_security_policy: null,
    strict_transport_security: null,
    x_frame_options: null,
    x_content_type_options: null,
    referrer_policy: null,
    permissions_policy: null,
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

describe('security summary', () => {
  it('returns a full score when checked signals are configured', () => {
    const result = getSecuritySummary(
      analysis({
        http: {
          http: probe({ reachable: true, final_url: 'https://example.com' }),
          https: probe({
            reachable: true,
            content_security_policy: "default-src 'self'",
            strict_transport_security: 'max-age=31536000',
            x_frame_options: 'DENY',
            x_content_type_options: 'nosniff',
            referrer_policy: 'strict-origin-when-cross-origin',
            permissions_policy: 'camera=()',
          }),
        },
        ssl: { valid: true, error: null, protocol: 'TLSv1.3', cipher: 'TLS_AES_128_GCM_SHA256', certificate: null },
      }),
    )

    expect(result.score).toBe(100)
    expect(result.findings).toEqual([])
  })

  it('deducts transparent weights and returns remediation for missing signals', () => {
    const result = getSecuritySummary(
      analysis({
        http: {
          http: probe({ reachable: true, final_url: 'http://example.com' }),
          https: probe({ reachable: true }),
        },
        ssl: {
          valid: true,
          error: null,
          protocol: 'TLSv1.3',
          cipher: 'TLS_AES_128_GCM_SHA256',
          certificate: {
            subject: 'example.com',
            san: ['example.com'],
            issuer: 'Example CA',
            issuer_org: 'Example CA',
            valid_from: null,
            valid_until: null,
            days_remaining: 10,
            expired: false,
            serial_number: null,
            fingerprint_sha256: null,
            signature_algorithm: null,
            version: 3,
          },
        },
      }),
    )

    expect(result.score).toBe(35)
    expect(result.findings.map((finding) => finding.id).sort()).toEqual([
      'http-not-redirected',
      'tls-expiring-soon',
      'missing-content_security_policy',
      'missing-strict_transport_security',
      'missing-x_frame_options',
      'missing-x_content_type_options',
      'missing-referrer_policy',
      'missing-permissions_policy',
    ].sort())
    expect(result.findings.find((finding) => finding.id === 'tls-expiring-soon')?.recommendation).toContain('Renew')
  })

  it('does not invent a score when the checks are unavailable', () => {
    const result = getSecuritySummary(
      analysis({
        analysis_errors: [
          { check: 'http', code: 'http_unavailable', message: 'HTTP unavailable' },
          { check: 'ssl', code: 'ssl_unavailable', message: 'TLS unavailable' },
        ],
      }),
    )

    expect(result.score).toBeNull()
    expect(result.findings.map((finding) => finding.id)).toEqual(['http-check-unavailable', 'tls-check-unavailable'])
  })
})
