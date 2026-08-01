import type {
  AnalysisError,
  AnalysisCheckMetadata,
  AnalysisMetadata,
  AnalysisProgress,
  AnalysisJob,
  CAARecord,
  DNSData,
  DomainAnalysis,
  ErrorDetails,
  ErrorPayload,
  GeoIPRecord,
  HTTPData,
  HTTPProbeResult,
  LatencyData,
  LatencyResult,
  MXRecord,
  PortResult,
  PortsData,
  Propagation,
  PropagationServer,
  SOARecord,
  SSLData,
  SSLCertificate,
} from './types'

type UnknownRecord = Record<string, unknown>
type Guard<T> = (value: unknown) => value is T

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean'
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isInteger(value: unknown): value is number {
  return isFiniteNumber(value) && Number.isInteger(value)
}

function isDateString(value: unknown): value is string {
  return isString(value) && !Number.isNaN(Date.parse(value))
}

function isNullable<T>(value: unknown, guard: Guard<T>): value is T | null {
  return value === null || guard(value)
}

function isArrayOf<T>(value: unknown, guard: Guard<T>): value is T[] {
  return Array.isArray(value) && value.every(guard)
}

function isStringArray(value: unknown): value is string[] {
  return isArrayOf(value, isString)
}

function isErrorDetails(value: unknown): value is ErrorDetails {
  if (!isRecord(value)) {
    return false
  }

  return (
    (value.loc === undefined || isStringArray(value.loc)) &&
    (value.message === undefined || isString(value.message))
  )
}

export function isErrorPayload(value: unknown): value is ErrorPayload {
  if (!isRecord(value) || !isString(value.code) || !isString(value.message)) {
    return false
  }

  return value.details === undefined || isArrayOf(value.details, isErrorDetails)
}

function isAnalysisError(value: unknown): value is AnalysisError {
  return (
    isRecord(value) &&
    isString(value.check) &&
    isString(value.code) &&
    isString(value.message)
  )
}

function isAnalysisMetadataStatus(value: unknown): value is AnalysisCheckMetadata['status'] {
  return value === 'successful' || value === 'failed' || value === 'timeout' || value === 'cancelled'
}

function isAnalysisCheckMetadata(value: unknown): value is AnalysisCheckMetadata {
  return (
    isRecord(value) &&
    isAnalysisMetadataStatus(value.status) &&
    isDateString(value.completed_at) &&
    isFiniteNumber(value.duration_ms) &&
    value.duration_ms >= 0 &&
    isStringArray(value.sources)
  )
}

function isAnalysisMetadata(value: unknown): value is AnalysisMetadata {
  return (
    isRecord(value) &&
    isDateString(value.started_at) &&
    isDateString(value.completed_at) &&
    isFiniteNumber(value.duration_ms) &&
    value.duration_ms >= 0 &&
    isRecord(value.checks) &&
    Object.values(value.checks).every(isAnalysisCheckMetadata)
  )
}

function isAnalysisProgress(value: unknown): value is AnalysisProgress {
  return (
    isRecord(value) &&
    isString(value.check) &&
    (value.status === 'queued' ||
      value.status === 'running' ||
      value.status === 'successful' ||
      value.status === 'partial' ||
      value.status === 'failed') &&
    isNullable(value.duration_ms, isFiniteNumber)
  )
}

function isMXRecord(value: unknown): value is MXRecord {
  return isRecord(value) && isInteger(value.priority) && isString(value.exchange)
}

function isSOARecord(value: unknown): value is SOARecord {
  return (
    isRecord(value) &&
    isString(value.mname) &&
    isString(value.rname) &&
    isInteger(value.serial) &&
    isInteger(value.refresh) &&
    isInteger(value.retry) &&
    isInteger(value.expire) &&
    isInteger(value.minimum)
  )
}

function isCAARecord(value: unknown): value is CAARecord {
  return isRecord(value) && isInteger(value.flags) && isString(value.tag) && isString(value.value)
}

function isPropagationServer(value: unknown): value is PropagationServer {
  return (
    isRecord(value) &&
    isString(value.name) &&
    isString(value.ip) &&
    isStringArray(value.A) &&
    isStringArray(value.AAAA) &&
    (value.status === 'ok' || value.status === 'timeout' || value.status === 'error')
  )
}

function isPropagation(value: unknown): value is Propagation {
  return isRecord(value) && isBoolean(value.consistent) && isArrayOf(value.servers, isPropagationServer)
}

function isDNSData(value: unknown): value is DNSData {
  return (
    isRecord(value) &&
    isStringArray(value.A) &&
    isStringArray(value.AAAA) &&
    isArrayOf(value.MX, isMXRecord) &&
    isStringArray(value.TXT) &&
    isStringArray(value.CNAME) &&
    isStringArray(value.NS) &&
    isNullable(value.SOA, isSOARecord) &&
    isArrayOf(value.CAA, isCAARecord) &&
    isRecord(value.PTR) &&
    Object.values(value.PTR).every((entry) => entry === null || isString(entry)) &&
    isNullable(value.propagation, isPropagation)
  )
}

function isGeoIPRecord(value: unknown): value is GeoIPRecord {
  if (!isRecord(value) || !isString(value.ip)) {
    return false
  }

  const stringFields = [
    'country',
    'country_code',
    'region',
    'city',
    'zip',
    'timezone',
    'isp',
    'org',
    'asn',
    'asn_name',
  ]
  const numberFields = ['lat', 'lon']

  return (
    stringFields.every((field) => isNullable(value[field], isString)) &&
    numberFields.every((field) => isNullable(value[field], isFiniteNumber))
  )
}

function isHTTPProbeResult(value: unknown): value is HTTPProbeResult {
  if (
    !isRecord(value) ||
    !isBoolean(value.reachable) ||
    !isNullable(value.status_code, isInteger) ||
    !isNullable(value.final_url, isString) ||
    !isStringArray(value.redirect_chain) ||
    !isNullable(value.response_time_ms, isInteger)
  ) {
    return false
  }

  const stringFields = [
    'server',
    'x_powered_by',
    'via',
    'content_type',
    'cache_control',
    'content_security_policy',
    'strict_transport_security',
    'x_frame_options',
    'x_content_type_options',
    'referrer_policy',
    'permissions_policy',
  ]

  return stringFields.every((field) => isNullable(value[field], isString))
}

function isHTTPData(value: unknown): value is HTTPData {
  return isRecord(value) && isNullable(value.http, isHTTPProbeResult) && isNullable(value.https, isHTTPProbeResult)
}

function isSSLCertificate(value: unknown): value is SSLCertificate {
  if (
    !isRecord(value) ||
    !isNullable(value.subject, isString) ||
    !isStringArray(value.san) ||
    !isNullable(value.issuer, isString) ||
    !isNullable(value.issuer_org, isString) ||
    !isNullable(value.valid_from, isDateString) ||
    !isNullable(value.valid_until, isDateString) ||
    !isNullable(value.days_remaining, isInteger) ||
    !isBoolean(value.expired)
  ) {
    return false
  }

  return (
    isNullable(value.serial_number, isString) &&
    isNullable(value.fingerprint_sha256, isString) &&
    isNullable(value.signature_algorithm, isString) &&
    isNullable(value.version, isInteger)
  )
}

function isSSLData(value: unknown): value is SSLData {
  return (
    isRecord(value) &&
    isBoolean(value.valid) &&
    isNullable(value.error, isString) &&
    isNullable(value.protocol, isString) &&
    isNullable(value.cipher, isString) &&
    isNullable(value.certificate, isSSLCertificate)
  )
}

function isPortResult(value: unknown): value is PortResult {
  return (
    isRecord(value) &&
    isInteger(value.port) &&
    isBoolean(value.open) &&
    (value.status === 'open' || value.status === 'closed' || value.status === 'filtered') &&
    isNullable(value.service, isString)
  )
}

function isPortsData(value: unknown): value is PortsData {
  return isRecord(value) && isArrayOf(value.results, isPortResult)
}

function isLatencyResult(value: unknown): value is LatencyResult {
  return (
    isRecord(value) &&
    isInteger(value.min_ms) &&
    isInteger(value.avg_ms) &&
    isInteger(value.max_ms) &&
    isInteger(value.loss)
  )
}

function isLatencyData(value: unknown): value is LatencyData {
  return isRecord(value) && isNullable(value.tcp_80, isLatencyResult) && isNullable(value.tcp_443, isLatencyResult)
}

export function isDomainAnalysis(value: unknown): value is DomainAnalysis {
  return (
    isRecord(value) &&
    isString(value.domain) &&
    isNullable(value.rdap_server, isString) &&
    isStringArray(value.status) &&
    isStringArray(value.nameservers) &&
    isNullable(value.registrar, isString) &&
    isNullable(value.registration_date, isDateString) &&
    isNullable(value.expiration_date, isDateString) &&
    isNullable(value.updated_date, isDateString) &&
    isNullable(value.whois_server, isString) &&
    isDNSData(value.dns) &&
    isRecord(value.geoip) &&
    Object.values(value.geoip).every(isGeoIPRecord) &&
    isNullable(value.http, isHTTPData) &&
    isNullable(value.ssl, isSSLData) &&
    isNullable(value.ports, isPortsData) &&
    isNullable(value.latency, isLatencyData) &&
    (value.metadata === undefined || value.metadata === null || isAnalysisMetadata(value.metadata)) &&
    isArrayOf(value.analysis_errors, isAnalysisError)
  )
}

export function isAnalysisJob(value: unknown): value is AnalysisJob {
  return (
    isRecord(value) &&
    isString(value.id) &&
    isString(value.domain) &&
    (value.status === 'queued' ||
      value.status === 'running' ||
      value.status === 'completed' ||
      value.status === 'failed' ||
      value.status === 'cancelled') &&
    isDateString(value.created_at) &&
    isNullable(value.result, isDomainAnalysis) &&
    isNullable(value.error, isErrorPayload) &&
    isArrayOf(value.progress, isAnalysisProgress)
  )
}
