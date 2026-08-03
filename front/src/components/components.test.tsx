import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import AnalysisForm from './AnalysisForm'
import AnalysisProgress from './AnalysisProgress'
import AnalysisResults from './AnalysisResults'
import type { DomainAnalysis } from '../api/types'

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
    TXT: [],
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
  ports: {
    results: [{ port: 443, open: true, status: 'open', service: 'https' }],
  },
  latency: null,
  metadata: {
    started_at: '2026-08-01T10:00:00Z',
    completed_at: '2026-08-01T10:00:01Z',
    duration_ms: 1000,
    checks: {
      rdap: {
        status: 'failed',
        completed_at: '2026-08-01T10:00:00.100Z',
        duration_ms: 100,
        sources: ['https://data.iana.org', 'https://rdap.example.test'],
      },
    },
  },
  analysis_errors: [
    { check: 'rdap', code: 'rdap_unavailable', message: 'RDAP provider unavailable' },
  ],
}

describe('frontend status components', () => {
  it('renders queued and running progress for a loading analysis', () => {
    const markup = renderToStaticMarkup(
      <AnalysisProgress
        progress={[
          { check: 'dns', status: 'queued', duration_ms: null },
          { check: 'http', status: 'running', duration_ms: null },
        ]}
      />,
    )

    expect(markup).toContain('aria-labelledby="progress-heading"')
    expect(markup).toContain('role="status"')
    expect(markup).toContain('0 of 2 checks complete, 1 running.')
    expect(markup).toContain('DNS records')
    expect(markup).toContain('HTTP and HTTPS')
    expect(markup).toContain('Running')
  })

  it('renders partial results and actionable accessibility landmarks', () => {
    const markup = renderToStaticMarkup(<AnalysisResults analysis={analysis} />)

    expect(markup).toContain('Analysis report')
    expect(markup).toContain('Some checks were unavailable')
    expect(markup).toContain('aria-label="Analysis warnings"')
    expect(markup).toContain('RDAP provider unavailable')
    expect(markup).toContain('Security signals')
    expect(markup).toContain('<div class="security-summary-heading"><h3 id="security-signals-heading">Security signals</h3><span class="security-score')
    expect(markup).toContain('<h3 id="registration-heading">Registration</h3>')
    expect(markup).toContain('<details class="result-details"><summary>Results</summary>')
    expect(markup).not.toContain('<details class="result-details" open>')
    expect(markup).not.toContain('<details class="metadata-details" open>')
    expect(markup).not.toContain('Heuristic review')
    expect(markup).toContain('Freshness and sources')
    expect(markup).toContain('https://data.iana.org')
    expect(markup).toContain('scope="col"')
    expect(markup).toContain('scope="row"')
  })

  it('keeps the domain form accessible and exposes cancellation while loading', () => {
    const onChange = () => undefined
    const onCancel = () => undefined
    const onSubmit = () => undefined

    const idleMarkup = renderToStaticMarkup(
      <AnalysisForm
        domain="example.com"
        loading={false}
        onChange={onChange}
        onCancel={onCancel}
        onSubmit={onSubmit}
      />,
    )
    const loadingMarkup = renderToStaticMarkup(
      <AnalysisForm
        domain="example.com"
        loading
        onChange={onChange}
        onCancel={onCancel}
        onSubmit={onSubmit}
      />,
    )

    expect(idleMarkup).toContain('for="domain-input"')
    expect(idleMarkup).toContain('aria-describedby="domain-help"')
    expect(idleMarkup).toContain('Analyze domain')
    expect(loadingMarkup).toContain('disabled')
    expect(loadingMarkup).toContain('Cancel')
  })
})
