import { describe, expect, it } from 'vitest'

import type { DomainAnalysis } from '../api/types'
import { filenameForDomain, formatAnalysisJson, formatAnalysisMarkdown } from './export'

const analysis: DomainAnalysis = {
  domain: 'example.com',
  rdap_server: null,
  status: ['active'],
  nameservers: ['ns1.example.com'],
  registrar: 'Example Registrar',
  registration_date: '2020-01-01T00:00:00Z',
  expiration_date: null,
  updated_date: null,
  whois_server: null,
  dns: {
    A: ['192.0.2.1'],
    AAAA: [],
    MX: [],
    TXT: ['v=spf1 | test'],
    CNAME: [],
    NS: ['ns1.example.com'],
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
  metadata: {
    started_at: '2026-08-01T10:00:00Z',
    completed_at: '2026-08-01T10:00:01Z',
    duration_ms: 1000,
    checks: {
      dns: {
        status: 'successful',
        completed_at: '2026-08-01T10:00:00.500Z',
        duration_ms: 500,
        sources: ['dns://8.8.8.8'],
      },
    },
  },
  analysis_errors: [{ check: 'rdap', code: 'rdap_unavailable', message: 'Provider unavailable' }],
}

describe('report export', () => {
  it('serializes the complete report as JSON', () => {
    const result = formatAnalysisJson(analysis)

    expect(JSON.parse(result)).toEqual(analysis)
    expect(result).toContain('"domain": "example.com"')
  })

  it('renders a readable Markdown report and escapes table separators', () => {
    const result = formatAnalysisMarkdown(analysis, new Date('2026-08-01T12:00:00Z'))

    expect(result).toContain('# Domain Analyzer report')
    expect(result).toContain('| Exported at | 2026-08-01T12:00:00.000Z |')
    expect(result).toContain('| rdap | rdap_unavailable | Provider unavailable |')
    expect(result).toContain('## Freshness and sources')
    expect(result).toContain('| dns | successful | 2026-08-01T10:00:00.500Z | 500 ms | dns://8.8.8.8 |')
    expect(result).toContain('v=spf1 \\| test')
    expect(result).toContain('## Security signals')
    expect(result).toContain('HTTP security signals could not be assessed')
  })

  it('creates safe filenames for domains', () => {
    expect(filenameForDomain('Example.COM', 'json')).toBe('example.com.json')
    expect(filenameForDomain('https://example.com/path', 'md')).toBe('https_example.com_path.md')
    expect(filenameForDomain('...', 'json')).toBe('domain-analysis.json')
  })
})
