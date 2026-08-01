import type { ReactNode } from 'react'

import type {
  DomainAnalysis,
  HTTPProbeResult,
  LatencyResult,
  Propagation,
  SSLData,
} from '../api/types'
import {
  downloadFile,
  filenameForDomain,
  formatAnalysisJson,
  formatAnalysisMarkdown,
} from '../utils/export'
import SecuritySummary from './SecuritySummary'

interface AnalysisResultsProps {
  analysis: DomainAnalysis
}

interface ResultSectionProps {
  title: string
  description?: string
  wide?: boolean
  children: ReactNode
}

function headingId(title: string) {
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `${slug || 'result'}-heading`
}

function ResultSection({ title, description, wide = false, children }: ResultSectionProps) {
  const id = headingId(title)

  return (
    <section className={`result-section${wide ? ' result-section-wide' : ''}`} aria-labelledby={id}>
      <div className="section-heading">
        <h3 id={id}>{title}</h3>
        {description && <p>{description}</p>}
      </div>
      {children}
    </section>
  )
}

function EmptyState({ children = 'No data available.' }: { children?: ReactNode }) {
  return <p className="empty-state">{children}</p>
}

function StringList({ values, empty = 'No records returned.' }: { values: string[]; empty?: string }) {
  if (values.length === 0) {
    return <EmptyState>{empty}</EmptyState>
  }

  return (
    <ul className="value-list">
      {values.map((value, index) => (
        <li key={`${value}-${index}`}>{value}</li>
      ))}
    </ul>
  )
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  const displayValue = value === null || value === undefined || value === '' ? '—' : value

  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{displayValue}</dd>
    </div>
  )
}

function formatDate(value: string | null) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString()
}

function SummaryCard({ label, value }: { label: string; value: ReactNode }) {
  const displayValue = value === null || value === undefined || value === '' ? '—' : value

  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{displayValue}</strong>
    </div>
  )
}

function DNSRecords({ analysis }: { analysis: DomainAnalysis }) {
  const { dns } = analysis
  const propagation = dns.propagation

  return (
    <ResultSection title="DNS records" description="Authoritative records and public resolver propagation.">
      <div className="record-groups">
        <div className="record-group">
          <h4>A</h4>
          <StringList values={dns.A} />
        </div>
        <div className="record-group">
          <h4>AAAA</h4>
          <StringList values={dns.AAAA} />
        </div>
        <div className="record-group">
          <h4>NS</h4>
          <StringList values={dns.NS} />
        </div>
        <div className="record-group">
          <h4>CNAME</h4>
          <StringList values={dns.CNAME} />
        </div>
        <div className="record-group">
          <h4>TXT</h4>
          <StringList values={dns.TXT} />
        </div>
        <div className="record-group">
          <h4>MX</h4>
          {dns.MX.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="value-list">
              {dns.MX.map((record, index) => (
                <li key={`${record.priority}-${record.exchange}-${index}`}>
                  <span className="record-badge">{record.priority}</span> {record.exchange}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="record-group">
          <h4>SOA</h4>
          {dns.SOA ? (
            <dl className="compact-fields">
              <Field label="Primary" value={dns.SOA.mname} />
              <Field label="Responsible" value={dns.SOA.rname} />
              <Field label="Serial" value={dns.SOA.serial} />
            </dl>
          ) : (
            <EmptyState />
          )}
        </div>
        <div className="record-group">
          <h4>CAA</h4>
          {dns.CAA.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="value-list">
              {dns.CAA.map((record, index) => (
                <li key={`${record.tag}-${record.value}-${index}`}>
                  {record.tag}: {record.value}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="propagation-block">
        <h4>Propagation</h4>
        <PropagationTable propagation={propagation} />
      </div>
    </ResultSection>
  )
}

function PropagationTable({ propagation }: { propagation: Propagation | null }) {
  if (!propagation) {
    return <EmptyState />
  }

  return (
    <div>
      <p className={`inline-status ${propagation.consistent ? 'status-good' : 'status-warning'}`}>
        {propagation.consistent ? 'Records are consistent' : 'Resolvers returned different records'}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Resolver</th>
              <th scope="col">A</th>
              <th scope="col">AAAA</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {propagation.servers.map((server, index) => (
              <tr key={`${server.ip}-${index}`}>
                <th scope="row">
                  {server.name}
                  <span className="table-subtitle">{server.ip}</span>
                </th>
                <td>{server.A.join(', ') || '—'}</td>
                <td>{server.AAAA.join(', ') || '—'}</td>
                <td>
                  <span className={`status-pill status-${server.status}`}>{server.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function GeoIPResults({ analysis }: { analysis: DomainAnalysis }) {
  const records = Object.values(analysis.geoip)

  return (
    <ResultSection title="GeoIP & ASN" description="Location and network ownership for resolved addresses.">
      {records.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">IP address</th>
                <th scope="col">Location</th>
                <th scope="col">Organization</th>
                <th scope="col">ASN</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.ip}>
                  <th scope="row">{record.ip}</th>
                  <td>{[record.city, record.region, record.country].filter(Boolean).join(', ') || '—'}</td>
                  <td>{record.org || record.isp || '—'}</td>
                  <td>{[record.asn, record.asn_name].filter(Boolean).join(' ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ResultSection>
  )
}

function HTTPProbe({ label, probe }: { label: string; probe: HTTPProbeResult | null }) {
  if (!probe) {
    return (
      <div className="probe-card">
        <h4>{label}</h4>
        <EmptyState />
      </div>
    )
  }

  return (
    <div className="probe-card">
      <div className="probe-title-row">
        <h4>{label}</h4>
        <span className={`status-pill ${probe.reachable ? 'status-ok' : 'status-error'}`}>
          {probe.reachable ? 'Reachable' : 'Unavailable'}
        </span>
      </div>
      <dl className="compact-fields">
        <Field label="Status" value={probe.status_code} />
        <Field
          label="Response"
          value={probe.response_time_ms === null ? '—' : `${probe.response_time_ms} ms`}
        />
        <Field label="Server" value={probe.server} />
        <Field label="Content type" value={probe.content_type} />
        <Field label="Final URL" value={probe.final_url} />
      </dl>
      {probe.redirect_chain.length > 0 && (
        <details>
          <summary>{probe.redirect_chain.length} redirect(s)</summary>
          <StringList values={probe.redirect_chain} />
        </details>
      )}
    </div>
  )
}

function HTTPResults({ analysis }: { analysis: DomainAnalysis }) {
  return (
    <ResultSection title="HTTP & HTTPS" description="Reachability, response timing, redirects, and selected headers.">
      {!analysis.http ? (
        <EmptyState />
      ) : (
        <div className="probe-grid">
          <HTTPProbe label="HTTP" probe={analysis.http.http} />
          <HTTPProbe label="HTTPS" probe={analysis.http.https} />
        </div>
      )}
    </ResultSection>
  )
}

function TLSResults({ ssl }: { ssl: SSLData | null }) {
  return (
    <ResultSection title="TLS certificate" description="Certificate validity and negotiated connection details.">
      {!ssl ? (
        <EmptyState />
      ) : (
        <div className="tls-content">
          <div className={`tls-status ${ssl.valid ? 'status-good' : 'status-warning'}`}>
            <strong>{ssl.valid ? 'Certificate is valid' : 'Certificate validation failed'}</strong>
            {ssl.error && <span>{ssl.error}</span>}
          </div>
          <dl className="detail-grid">
            <Field label="Protocol" value={ssl.protocol} />
            <Field label="Cipher" value={ssl.cipher} />
            <Field label="Subject" value={ssl.certificate?.subject} />
            <Field label="Issuer" value={ssl.certificate?.issuer} />
            <Field label="Valid from" value={formatDate(ssl.certificate?.valid_from || null)} />
            <Field label="Valid until" value={formatDate(ssl.certificate?.valid_until || null)} />
            <Field label="Days remaining" value={ssl.certificate?.days_remaining} />
            <Field label="Signature" value={ssl.certificate?.signature_algorithm} />
          </dl>
          {ssl.certificate?.san && ssl.certificate.san.length > 0 && (
            <div className="subsection">
              <h4>Subject alternative names</h4>
              <StringList values={ssl.certificate.san} />
            </div>
          )}
        </div>
      )}
    </ResultSection>
  )
}

function NetworkResults({ analysis }: { analysis: DomainAnalysis }) {
  return (
    <ResultSection title="Ports & latency" description="Common TCP service ports and connection timing.">
      <div className="network-grid">
        <div>
          <h4>Port scan</h4>
          {!analysis.ports || analysis.ports.results.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Port</th>
                    <th scope="col">Service</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.ports.results.map((result) => (
                    <tr key={result.port}>
                      <th scope="row">{result.port}</th>
                      <td>{result.service || '—'}</td>
                      <td>
                        <span className={`status-pill status-${result.status}`}>{result.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div>
          <h4>TCP latency</h4>
          {!analysis.latency ? (
            <EmptyState />
          ) : (
            <div className="latency-list">
              <LatencyCard label="Port 80" result={analysis.latency.tcp_80} />
              <LatencyCard label="Port 443" result={analysis.latency.tcp_443} />
            </div>
          )}
        </div>
      </div>
    </ResultSection>
  )
}

function LatencyCard({ label, result }: { label: string; result: LatencyResult | null }) {
  return (
    <div className="latency-card">
      <strong>{label}</strong>
      {!result ? (
        <EmptyState />
      ) : (
        <dl className="compact-fields">
          <Field label="Min" value={`${result.min_ms} ms`} />
          <Field label="Average" value={`${result.avg_ms} ms`} />
          <Field label="Max" value={`${result.max_ms} ms`} />
          <Field label="Loss" value={result.loss} />
        </dl>
      )}
    </div>
  )
}

function AnalysisResults({ analysis }: AnalysisResultsProps) {
  const exportJson = () => {
    downloadFile(formatAnalysisJson(analysis), filenameForDomain(analysis.domain, 'json'), 'application/json')
  }

  const exportMarkdown = () => {
    downloadFile(formatAnalysisMarkdown(analysis), filenameForDomain(analysis.domain, 'md'), 'text/markdown')
  }

  return (
    <section className="analysis-results" aria-labelledby="results-heading">
      <div className="results-heading">
        <div>
          <p className="eyebrow">Analysis report</p>
          <h2 id="results-heading">{analysis.domain}</h2>
        </div>
        <div className="results-actions">
          <span className="result-state">Complete with {analysis.analysis_errors.length} warning(s)</span>
          <div className="export-actions" aria-label="Export report">
            <button type="button" className="button button-secondary" onClick={exportJson}>
              JSON
            </button>
            <button type="button" className="button button-secondary" onClick={exportMarkdown}>
              Markdown
            </button>
          </div>
        </div>
      </div>

      <div className="summary-grid">
        <SummaryCard label="Registrar" value={analysis.registrar} />
        <SummaryCard label="Status" value={analysis.status.join(', ')} />
        <SummaryCard label="RDAP server" value={analysis.rdap_server} />
        <SummaryCard label="Nameservers" value={analysis.nameservers.length} />
      </div>

      {analysis.analysis_errors.length > 0 && (
        <aside className="warning-panel" aria-label="Analysis warnings">
          <strong>Some checks were unavailable</strong>
          <ul>
            {analysis.analysis_errors.map((error) => (
              <li key={error.check}>
                <span>{error.check}</span> {error.message}
              </li>
            ))}
          </ul>
        </aside>
      )}

      <SecuritySummary analysis={analysis} />

      <div className="detail-grid result-grid">
        <ResultSection title="Registration" description="RDAP registration metadata.">
          <dl className="compact-fields">
            <Field label="Registrar" value={analysis.registrar} />
            <Field label="Registered" value={formatDate(analysis.registration_date)} />
            <Field label="Expires" value={formatDate(analysis.expiration_date)} />
            <Field label="Updated" value={formatDate(analysis.updated_date)} />
            <Field label="WHOIS" value={analysis.whois_server} />
          </dl>
          <div className="subsection">
            <h4>Nameservers</h4>
            <StringList values={analysis.nameservers} />
          </div>
        </ResultSection>
        <DNSRecords analysis={analysis} />
        <GeoIPResults analysis={analysis} />
        <HTTPResults analysis={analysis} />
        <TLSResults ssl={analysis.ssl} />
        <NetworkResults analysis={analysis} />
      </div>
    </section>
  )
}

export default AnalysisResults
