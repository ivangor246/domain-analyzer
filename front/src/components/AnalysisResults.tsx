import type { ReactNode } from 'react'

import type {
  AnalysisMetadata,
  DomainAnalysis,
  HTTPProbeResult,
  LatencyResult,
  Propagation,
  SSLData,
} from '../api/types'
import { useI18n } from '../i18n-context'
import type { Translate } from '../i18n-utils'
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
  const slug = title
    .toLocaleLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-|-$/g, '')
  return `${slug || 'result'}-heading`
}

function localizedValue(value: string, t: Translate) {
  const translationKey = `status.${value}`
  const translation = t(translationKey)
  return translation === translationKey ? value : translation
}

function localizedCheck(value: string, t: Translate) {
  const translation = t(value)
  return translation === value ? value.replaceAll('_', ' ') : translation
}

function ResultSection({ title, description, wide = false, children }: ResultSectionProps) {
  const { t } = useI18n()
  const id = headingId(title)

  return (
    <section className={`result-section${wide ? ' result-section-wide' : ''}`} aria-labelledby={id}>
      <div className="section-heading">
        <h3 id={id}>{title}</h3>
        {description && <p>{description}</p>}
      </div>
      <details className="result-details" open>
        <summary>{t('showResults')}</summary>
        <div className="result-details-content">{children}</div>
      </details>
    </section>
  )
}

function EmptyState({ children }: { children?: ReactNode }) {
  const { t } = useI18n()

  return <p className="empty-state">{children ?? t('emptyData')}</p>
}

function StringList({ values, empty }: { values: string[]; empty?: string }) {
  const { t } = useI18n()

  if (values.length === 0) {
    return <EmptyState>{empty ?? t('noRecords')}</EmptyState>
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

function formatDate(value: string | null, locale: string) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(locale)
}

function formatDateTime(value: string, locale: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })
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
  const { t } = useI18n()
  const { dns } = analysis
  const propagation = dns.propagation

  return (
    <ResultSection title={t('dnsRecords')} description={t('dnsDescription')}>
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
              <Field label={t('primary')} value={dns.SOA.mname} />
              <Field label={t('responsible')} value={dns.SOA.rname} />
              <Field label={t('serial')} value={dns.SOA.serial} />
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
        <h4>{t('propagation')}</h4>
        <PropagationTable propagation={propagation} />
      </div>
    </ResultSection>
  )
}

function PropagationTable({ propagation }: { propagation: Propagation | null }) {
  const { t } = useI18n()

  if (!propagation) {
    return <EmptyState />
  }

  return (
    <div>
      <p className={`inline-status ${propagation.consistent ? 'status-good' : 'status-warning'}`}>
        {propagation.consistent ? t('recordsConsistent') : t('recordsInconsistent')}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">{t('resolver')}</th>
              <th scope="col">A</th>
              <th scope="col">AAAA</th>
              <th scope="col">{t('status')}</th>
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
                  <span className={`status-pill status-${server.status}`}>{localizedValue(server.status, t)}</span>
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
  const { t } = useI18n()
  const records = Object.values(analysis.geoip)

  return (
    <ResultSection title={t('geoipAsn')} description={t('geoipDescription')}>
      {records.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">{t('ipAddress')}</th>
                <th scope="col">{t('location')}</th>
                <th scope="col">{t('organization')}</th>
                <th scope="col">{t('asn')}</th>
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
  const { t } = useI18n()

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
          {probe.reachable ? t('reachable') : t('unavailable')}
        </span>
      </div>
      <dl className="compact-fields">
        <Field label={t('status')} value={probe.status_code} />
        <Field
          label={t('response')}
          value={probe.response_time_ms === null ? '—' : `${probe.response_time_ms} ms`}
        />
        <Field label={t('server')} value={probe.server} />
        <Field label={t('contentType')} value={probe.content_type} />
        <Field label={t('finalUrl')} value={probe.final_url} />
      </dl>
      {probe.redirect_chain.length > 0 && (
        <details open>
          <summary>{t('redirects', { count: probe.redirect_chain.length })}</summary>
          <StringList values={probe.redirect_chain} />
        </details>
      )}
    </div>
  )
}

function HTTPResults({ analysis }: { analysis: DomainAnalysis }) {
  const { t } = useI18n()

  return (
    <ResultSection title={t('httpHttps')} description={t('httpDescription')}>
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
  const { locale, t } = useI18n()

  return (
    <ResultSection title={t('tlsCertificate')} description={t('tlsDescription')}>
      {!ssl ? (
        <EmptyState />
      ) : (
        <div className="tls-content">
          <div className={`tls-status ${ssl.valid ? 'status-good' : 'status-warning'}`}>
            <strong>{ssl.valid ? t('certificateValid') : t('certificateFailed')}</strong>
            {ssl.error && <span>{ssl.error}</span>}
          </div>
          <dl className="detail-grid">
            <Field label={t('protocol')} value={ssl.protocol} />
            <Field label={t('cipher')} value={ssl.cipher} />
            <Field label={t('subject')} value={ssl.certificate?.subject} />
            <Field label={t('issuer')} value={ssl.certificate?.issuer} />
            <Field label={t('validFrom')} value={formatDate(ssl.certificate?.valid_from || null, locale)} />
            <Field label={t('validUntil')} value={formatDate(ssl.certificate?.valid_until || null, locale)} />
            <Field label={t('daysRemaining')} value={ssl.certificate?.days_remaining} />
            <Field label={t('signature')} value={ssl.certificate?.signature_algorithm} />
          </dl>
          {ssl.certificate?.san && ssl.certificate.san.length > 0 && (
            <div className="subsection">
              <h4>{t('subjectAlternativeNames')}</h4>
              <StringList values={ssl.certificate.san} />
            </div>
          )}
        </div>
      )}
    </ResultSection>
  )
}

function NetworkResults({ analysis }: { analysis: DomainAnalysis }) {
  const { t } = useI18n()

  return (
    <ResultSection title={t('portsLatency')} description={t('portsDescription')}>
      <div className="network-grid">
        <div>
          <h4>{t('portScan')}</h4>
          {!analysis.ports || analysis.ports.results.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t('port')}</th>
                    <th scope="col">{t('service')}</th>
                    <th scope="col">{t('status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.ports.results.map((result) => (
                    <tr key={result.port}>
                      <th scope="row">{result.port}</th>
                      <td>{result.service || '—'}</td>
                      <td>
                        <span className={`status-pill status-${result.status}`}>{localizedValue(result.status, t)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div>
          <h4>{t('latency')}</h4>
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
  const { t } = useI18n()

  return (
    <div className="latency-card">
      <strong>{label}</strong>
      {!result ? (
        <EmptyState />
      ) : (
        <dl className="compact-fields">
          <Field label={t('min')} value={`${result.min_ms} ms`} />
          <Field label={t('average')} value={`${result.avg_ms} ms`} />
          <Field label={t('max')} value={`${result.max_ms} ms`} />
          <Field label={t('loss')} value={result.loss} />
        </dl>
      )}
    </div>
  )
}

function AnalysisMetadataPanel({ metadata }: { metadata?: AnalysisMetadata | null }) {
  const { locale, t } = useI18n()

  if (!metadata) {
    return null
  }

  return (
    <section className="metadata-panel" aria-labelledby="metadata-heading">
      <div className="section-heading">
        <h3 id="metadata-heading">{t('freshnessSources')}</h3>
        <p>{t('freshnessDescription')}</p>
      </div>
      <div className="metadata-summary">
        <SummaryCard label={t('completed')} value={formatDateTime(metadata.completed_at, locale)} />
        <SummaryCard label={t('analysisDuration')} value={`${metadata.duration_ms} ms`} />
        <SummaryCard label={t('checksReported')} value={Object.keys(metadata.checks).length} />
      </div>
      {Object.keys(metadata.checks).length > 0 && (
        <details className="metadata-details" open>
          <summary>{t('checkSources')}</summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t('check')}</th>
                  <th scope="col">{t('status')}</th>
                  <th scope="col">{t('completed')}</th>
                  <th scope="col">{t('duration')}</th>
                  <th scope="col">{t('source')}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(metadata.checks).map(([check, details]) => (
                  <tr key={check}>
                    <th scope="row">{localizedCheck(check, t)}</th>
                    <td>
                      <span className={`status-pill status-${details.status}`}>
                        {localizedValue(details.status, t)}
                      </span>
                    </td>
                    <td>{formatDateTime(details.completed_at, locale)}</td>
                    <td>{details.duration_ms} ms</td>
                    <td>{details.sources.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  )
}

function AnalysisResults({ analysis }: AnalysisResultsProps) {
  const { locale, t } = useI18n()
  const warningCount = analysis.analysis_errors.length

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
          <p className="eyebrow">{t('analysisReport')}</p>
          <h2 id="results-heading">{analysis.domain}</h2>
        </div>
        <div className="results-actions">
          <span className="result-state">
            {t('completeWithWarnings', {
              count: warningCount,
              warningLabel: t(warningCount === 1 ? 'warning' : 'warnings'),
            })}
          </span>
          <div className="export-actions" aria-label={t('exportReport')}>
            <button type="button" className="button button-secondary" onClick={exportJson}>
              {t('json')}
            </button>
            <button type="button" className="button button-secondary" onClick={exportMarkdown}>
              {t('markdown')}
            </button>
          </div>
        </div>
      </div>

      <div className="summary-grid">
        <SummaryCard label={t('registrar')} value={analysis.registrar} />
        <SummaryCard label={t('status')} value={analysis.status.map((status) => localizedValue(status, t)).join(', ')} />
        <SummaryCard label={t('rdapServer')} value={analysis.rdap_server} />
        <SummaryCard label={t('nameservers')} value={analysis.nameservers.length} />
      </div>

      {warningCount > 0 && (
        <aside className="warning-panel" aria-label={t('analysisWarnings')}>
          <strong>{t('someChecksUnavailable')}</strong>
          <ul>
            {analysis.analysis_errors.map((error) => (
              <li key={error.check}>
                <span>{localizedCheck(error.check, t)}</span> {error.message}
              </li>
            ))}
          </ul>
        </aside>
      )}

      <AnalysisMetadataPanel metadata={analysis.metadata} />

      <SecuritySummary analysis={analysis} />

      <div className="detail-grid result-grid">
        <ResultSection title={t('registration')} description={t('registrationDescription')}>
          <dl className="compact-fields">
            <Field label={t('registrar')} value={analysis.registrar} />
            <Field label={t('registered')} value={formatDate(analysis.registration_date, locale)} />
            <Field label={t('expires')} value={formatDate(analysis.expiration_date, locale)} />
            <Field label={t('updated')} value={formatDate(analysis.updated_date, locale)} />
            <Field label="WHOIS" value={analysis.whois_server} />
          </dl>
          <div className="subsection">
            <h4>{t('nameservers')}</h4>
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
