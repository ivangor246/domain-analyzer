import type { DomainAnalysis, HTTPProbeResult, LatencyResult } from '../api/types'
import { getSecuritySummary } from './security'

function markdownCell(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  return String(value).replaceAll('|', '\\|').replaceAll('\n', '<br>')
}

function jsonCell(value: unknown): string {
  if (value === null || value === undefined) {
    return '—'
  }

  return JSON.stringify(value)
}

function listCell(values: string[]): string {
  return values.length > 0 ? values.join(', ') : '—'
}

function tableRow(label: string, value: unknown): string {
  return `| ${markdownCell(label)} | ${markdownCell(value)} |`
}

function probeRows(probe: HTTPProbeResult): string[] {
  return [
    tableRow('Reachable', probe.reachable ? 'Yes' : 'No'),
    tableRow('Status', probe.status_code),
    tableRow('Final URL', probe.final_url),
    tableRow('Redirect chain', listCell(probe.redirect_chain)),
    tableRow('Response time', probe.response_time_ms === null ? null : `${probe.response_time_ms} ms`),
    tableRow('Server', probe.server),
    tableRow('Content type', probe.content_type),
    tableRow('Content-Security-Policy', probe.content_security_policy),
    tableRow('Strict-Transport-Security', probe.strict_transport_security),
    tableRow('X-Frame-Options', probe.x_frame_options),
    tableRow('X-Content-Type-Options', probe.x_content_type_options),
    tableRow('Referrer-Policy', probe.referrer_policy),
    tableRow('Permissions-Policy', probe.permissions_policy),
  ]
}

function latencyRows(label: string, result: LatencyResult | null): string[] {
  if (!result) {
    return [tableRow(label, null)]
  }

  return [
    tableRow(`${label} minimum`, `${result.min_ms} ms`),
    tableRow(`${label} average`, `${result.avg_ms} ms`),
    tableRow(`${label} maximum`, `${result.max_ms} ms`),
    tableRow(`${label} loss`, result.loss),
  ]
}

export function formatAnalysisJson(analysis: DomainAnalysis): string {
  return `${JSON.stringify(analysis, null, 2)}\n`
}

export function formatAnalysisMarkdown(analysis: DomainAnalysis, exportedAt = new Date()): string {
  const securitySummary = getSecuritySummary(analysis)
  const lines = [
    '# Domain Analyzer report',
    '',
    tableRow('Domain', analysis.domain),
    tableRow('Exported at', exportedAt.toISOString()),
    '',
    '## Summary',
    '',
    '| Field | Value |',
    '| --- | --- |',
    tableRow('Registrar', analysis.registrar),
    tableRow('Status', listCell(analysis.status)),
    tableRow('RDAP server', analysis.rdap_server),
    tableRow('Nameservers', analysis.nameservers.length),
    '',
    '## Warnings',
    '',
  ]

  if (analysis.metadata) {
    lines.push(
      '## Freshness and sources',
      '',
      tableRow('Analyzed at', analysis.metadata.completed_at),
      tableRow('Analysis duration', `${analysis.metadata.duration_ms} ms`),
      '',
      '| Check | Status | Completed at | Duration | Sources |',
      '| --- | --- | --- | --- | --- |',
    )
    for (const [check, metadata] of Object.entries(analysis.metadata.checks)) {
      lines.push(
        `| ${markdownCell(check)} | ${markdownCell(metadata.status)} | ${markdownCell(metadata.completed_at)} | ${markdownCell(`${metadata.duration_ms} ms`)} | ${markdownCell(listCell(metadata.sources))} |`,
      )
    }
    lines.push('')
  }

  if (analysis.analysis_errors.length === 0) {
    lines.push('No check warnings were reported.', '')
  } else {
    lines.push('| Check | Code | Message |', '| --- | --- | --- |')
    for (const error of analysis.analysis_errors) {
      lines.push(`| ${markdownCell(error.check)} | ${markdownCell(error.code)} | ${markdownCell(error.message)} |`)
    }
    lines.push('')
  }

  lines.push(
    '## Security signals',
    '',
    'This is a heuristic signal check, not a complete security audit.',
    '',
    '| Field | Value |',
    '| --- | --- |',
    tableRow('Score', securitySummary.score === null ? 'Not assessed' : `${securitySummary.score}/100`),
    tableRow('Assessed signals', securitySummary.assessedSignals),
    '',
  )
  if (securitySummary.findings.length === 0) {
    lines.push('No actionable signals were found in the collected responses.', '')
  } else {
    lines.push('| Severity | Signal | Recommendation |', '| --- | --- | --- |')
    for (const finding of securitySummary.findings) {
      lines.push(
        `| ${markdownCell(finding.severity)} | ${markdownCell(finding.title)} | ${markdownCell(finding.recommendation)} |`,
      )
    }
    lines.push('')
  }

  lines.push(
    '## Registration',
    '',
    '| Field | Value |',
    '| --- | --- |',
    tableRow('Registered', analysis.registration_date),
    tableRow('Expires', analysis.expiration_date),
    tableRow('Updated', analysis.updated_date),
    tableRow('WHOIS server', analysis.whois_server),
    tableRow('Nameservers', listCell(analysis.nameservers)),
    '',
    '## DNS',
    '',
    '| Record | Value |',
    '| --- | --- |',
    tableRow('A', listCell(analysis.dns.A)),
    tableRow('AAAA', listCell(analysis.dns.AAAA)),
    tableRow('MX', listCell(analysis.dns.MX.map((record) => `${record.priority} ${record.exchange}`))),
    tableRow('TXT', listCell(analysis.dns.TXT)),
    tableRow('CNAME', listCell(analysis.dns.CNAME)),
    tableRow('NS', listCell(analysis.dns.NS)),
    tableRow('SOA', jsonCell(analysis.dns.SOA)),
    tableRow('CAA', listCell(analysis.dns.CAA.map((record) => `${record.tag}: ${record.value}`))),
    tableRow('PTR', jsonCell(analysis.dns.PTR)),
    tableRow('Propagation', jsonCell(analysis.dns.propagation)),
    '',
    '## GeoIP & ASN',
    '',
    '| IP address | Location | Organization | ASN |',
    '| --- | --- | --- | --- |',
  )

  const geoipRecords = Object.values(analysis.geoip)
  if (geoipRecords.length === 0) {
    lines.push('| — | No records returned. | — | — |')
  } else {
    for (const record of geoipRecords) {
      lines.push(
        `| ${markdownCell(record.ip)} | ${markdownCell([record.city, record.region, record.country].filter(Boolean).join(', '))} | ${markdownCell(record.org || record.isp)} | ${markdownCell([record.asn, record.asn_name].filter(Boolean).join(' '))} |`,
      )
    }
  }

  lines.push('', '## HTTP & HTTPS', '')
  for (const [label, probe] of [
    ['HTTP', analysis.http?.http ?? null],
    ['HTTPS', analysis.http?.https ?? null],
  ] as const) {
    lines.push(`### ${label}`, '', '| Field | Value |', '| --- | --- |')
    if (probe) {
      lines.push(...probeRows(probe))
    } else {
      lines.push(tableRow('Result', null))
    }
    lines.push('')
  }

  lines.push('## TLS', '', '| Field | Value |', '| --- | --- |')
  if (!analysis.ssl) {
    lines.push(tableRow('Result', null))
  } else {
    lines.push(
      tableRow('Valid', analysis.ssl.valid ? 'Yes' : 'No'),
      tableRow('Error', analysis.ssl.error),
      tableRow('Protocol', analysis.ssl.protocol),
      tableRow('Cipher', analysis.ssl.cipher),
      tableRow('Certificate', jsonCell(analysis.ssl.certificate)),
    )
  }

  lines.push('', '## Ports & latency', '', '| Field | Value |', '| --- | --- |')
  if (!analysis.ports) {
    lines.push(tableRow('Ports', null))
  } else {
    for (const result of analysis.ports.results) {
      lines.push(tableRow(`Port ${result.port}`, `${result.status}${result.service ? ` (${result.service})` : ''}`))
    }
  }
  lines.push(...latencyRows('TCP port 80', analysis.latency?.tcp_80 ?? null))
  lines.push(...latencyRows('TCP port 443', analysis.latency?.tcp_443 ?? null))
  lines.push('')

  return `${lines.join('\n')}\n`
}

export function filenameForDomain(domain: string, extension: 'json' | 'md'): string {
  const safeDomain = domain.toLowerCase().replace(/[^a-z0-9._-]+/g, '_').replace(/^\.+|\.+$/g, '')
  return `${safeDomain || 'domain-analysis'}.${extension}`
}

export function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
