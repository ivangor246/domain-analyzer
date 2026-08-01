import type { DomainAnalysis, HTTPProbeResult } from '../api/types'

export type FindingSeverity = 'high' | 'medium' | 'low' | 'info'

export interface SecurityFinding {
  id: string
  severity: FindingSeverity
  title: string
  recommendation: string
}

export interface SecuritySummary {
  score: number | null
  assessedSignals: number
  findings: SecurityFinding[]
}

const severityWeight: Record<FindingSeverity, number> = {
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
}

const headerChecks: Array<{
  field: keyof Pick<
    HTTPProbeResult,
    | 'content_security_policy'
    | 'strict_transport_security'
    | 'x_frame_options'
    | 'x_content_type_options'
    | 'referrer_policy'
    | 'permissions_policy'
  >
  title: string
  recommendation: string
  severity: Exclude<FindingSeverity, 'high' | 'info'>
  deduction: number
}> = [
  {
    field: 'content_security_policy',
    title: 'Content-Security-Policy is missing',
    recommendation: 'Define a restrictive Content-Security-Policy and tune it against the application resources.',
    severity: 'medium',
    deduction: 10,
  },
  {
    field: 'strict_transport_security',
    title: 'Strict-Transport-Security is missing',
    recommendation: 'Add HSTS on HTTPS responses after confirming that all covered hosts support HTTPS.',
    severity: 'medium',
    deduction: 10,
  },
  {
    field: 'x_frame_options',
    title: 'X-Frame-Options is missing',
    recommendation: 'Set a framing policy, preferably through Content-Security-Policy frame-ancestors.',
    severity: 'low',
    deduction: 5,
  },
  {
    field: 'x_content_type_options',
    title: 'X-Content-Type-Options is missing',
    recommendation: 'Send X-Content-Type-Options: nosniff for responses that contain user-controlled or executable content.',
    severity: 'low',
    deduction: 5,
  },
  {
    field: 'referrer_policy',
    title: 'Referrer-Policy is missing',
    recommendation: 'Set an explicit Referrer-Policy such as strict-origin-when-cross-origin.',
    severity: 'low',
    deduction: 5,
  },
  {
    field: 'permissions_policy',
    title: 'Permissions-Policy is missing',
    recommendation: 'Restrict browser features that the application does not need with Permissions-Policy.',
    severity: 'low',
    deduction: 5,
  },
]

function hasCheckError(analysis: DomainAnalysis, check: string) {
  return analysis.analysis_errors.some((error) => error.check === check)
}

function isMissing(value: string | null) {
  return !value || value.trim() === ''
}

function pushFinding(
  findings: SecurityFinding[],
  id: string,
  severity: FindingSeverity,
  title: string,
  recommendation: string,
) {
  findings.push({ id, severity, title, recommendation })
}

function addHTTPSFindings(
  https: HTTPProbeResult,
  http: HTTPProbeResult | null,
  findings: SecurityFinding[],
): number {
  let assessedSignals = 1

  if (!https.reachable) {
    pushFinding(
      findings,
      'https-unavailable',
      'high',
      'HTTPS is not reachable',
      'Serve the domain over HTTPS with a valid certificate and keep HTTP only as a redirect or compatibility endpoint.',
    )
    return assessedSignals
  }

  if (http?.reachable && !http.final_url?.startsWith('https://')) {
    pushFinding(
      findings,
      'http-not-redirected',
      'medium',
      'HTTP does not redirect to HTTPS',
      'Redirect HTTP requests to the canonical HTTPS URL to reduce accidental plaintext access.',
    )
  }

  for (const check of headerChecks) {
    assessedSignals += 1
    if (isMissing(https[check.field])) {
      pushFinding(findings, `missing-${check.field}`, check.severity, check.title, check.recommendation)
    }
  }

  return assessedSignals
}

function addTLSFindings(analysis: DomainAnalysis, findings: SecurityFinding[]): { assessedSignals: number; deductions: number } {
  if (!analysis.ssl || hasCheckError(analysis, 'ssl')) {
    pushFinding(
      findings,
      'tls-check-unavailable',
      'info',
      'TLS could not be assessed',
      'Run the TLS check again and verify that the target accepts connections on port 443.',
    )
    return { assessedSignals: 0, deductions: 0 }
  }

  let deductions = 0
  let assessedSignals = 1
  if (!analysis.ssl.valid) {
    deductions += 35
    pushFinding(
      findings,
      'tls-invalid',
      'high',
      'TLS certificate validation failed',
      'Renew or correctly configure the certificate chain, hostname coverage, and expiration settings.',
    )
  }

  const daysRemaining = analysis.ssl.certificate?.days_remaining
  if (daysRemaining !== null && daysRemaining !== undefined) {
    assessedSignals += 1
    if (daysRemaining <= 30) {
      deductions += 15
      pushFinding(
        findings,
        'tls-expiring-soon',
        daysRemaining <= 7 ? 'high' : 'medium',
        `TLS certificate expires in ${Math.max(daysRemaining, 0)} day(s)`,
        'Renew the certificate before expiration and confirm that automated renewal is working.',
      )
    }
  }

  return { assessedSignals, deductions }
}

export function getSecuritySummary(analysis: DomainAnalysis): SecuritySummary {
  const findings: SecurityFinding[] = []
  let assessedSignals = 0
  let deductions = 0

  if (!analysis.http || hasCheckError(analysis, 'http')) {
    pushFinding(
      findings,
      'http-check-unavailable',
      'info',
      'HTTP security signals could not be assessed',
      'Run the HTTP check again to inspect HTTPS reachability and response headers.',
    )
  } else if (analysis.http.https) {
    assessedSignals += addHTTPSFindings(analysis.http.https, analysis.http.http, findings)
    if (!analysis.http.https.reachable) {
      deductions += 35
    } else {
      for (const check of headerChecks) {
        if (isMissing(analysis.http.https[check.field])) {
          deductions += check.deduction
        }
      }
      if (analysis.http.http?.reachable && !analysis.http.http.final_url?.startsWith('https://')) {
        deductions += 10
      }
    }
  } else {
    pushFinding(
      findings,
      'https-check-unavailable',
      'info',
      'HTTPS security signals could not be assessed',
      'Run the HTTP check again to inspect HTTPS reachability and response headers.',
    )
  }

  const tls = addTLSFindings(analysis, findings)
  assessedSignals += tls.assessedSignals
  deductions += tls.deductions

  findings.sort((left, right) => severityWeight[right.severity] - severityWeight[left.severity])

  return {
    score: assessedSignals === 0 ? null : Math.max(0, 100 - deductions),
    assessedSignals,
    findings,
  }
}
