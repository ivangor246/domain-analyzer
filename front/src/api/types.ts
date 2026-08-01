export interface AnalysisError {
  check: string
  code: string
  message: string
}

export interface MXRecord {
  priority: number
  exchange: string
}

export interface SOARecord {
  mname: string
  rname: string
  serial: number
  refresh: number
  retry: number
  expire: number
  minimum: number
}

export interface CAARecord {
  flags: number
  tag: string
  value: string
}

export interface PropagationServer {
  name: string
  ip: string
  A: string[]
  AAAA: string[]
  status: 'ok' | 'timeout' | 'error'
}

export interface Propagation {
  consistent: boolean
  servers: PropagationServer[]
}

export interface DNSData {
  A: string[]
  AAAA: string[]
  MX: MXRecord[]
  TXT: string[]
  CNAME: string[]
  NS: string[]
  SOA: SOARecord | null
  CAA: CAARecord[]
  PTR: Record<string, string | null>
  propagation: Propagation | null
}

export interface GeoIPRecord {
  ip: string
  country: string | null
  country_code: string | null
  region: string | null
  city: string | null
  zip: string | null
  lat: number | null
  lon: number | null
  timezone: string | null
  isp: string | null
  org: string | null
  asn: string | null
  asn_name: string | null
}

export interface HTTPProbeResult {
  reachable: boolean
  status_code: number | null
  final_url: string | null
  redirect_chain: string[]
  response_time_ms: number | null
  server: string | null
  x_powered_by: string | null
  via: string | null
  content_type: string | null
  cache_control: string | null
  content_security_policy: string | null
  strict_transport_security: string | null
  x_frame_options: string | null
  x_content_type_options: string | null
  referrer_policy: string | null
  permissions_policy: string | null
}

export interface HTTPData {
  http: HTTPProbeResult | null
  https: HTTPProbeResult | null
}

export interface SSLCertificate {
  subject: string | null
  san: string[]
  issuer: string | null
  issuer_org: string | null
  valid_from: string | null
  valid_until: string | null
  days_remaining: number | null
  expired: boolean
  serial_number: string | null
  fingerprint_sha256: string | null
  signature_algorithm: string | null
  version: number | null
}

export interface SSLData {
  valid: boolean
  error: string | null
  protocol: string | null
  cipher: string | null
  certificate: SSLCertificate | null
}

export interface PortResult {
  port: number
  open: boolean
  status: 'open' | 'closed' | 'filtered'
  service: string | null
}

export interface PortsData {
  results: PortResult[]
}

export interface LatencyResult {
  min_ms: number
  avg_ms: number
  max_ms: number
  loss: number
}

export interface LatencyData {
  tcp_80: LatencyResult | null
  tcp_443: LatencyResult | null
}

export interface DomainAnalysis {
  domain: string
  rdap_server: string | null
  status: string[]
  nameservers: string[]
  registrar: string | null
  registration_date: string | null
  expiration_date: string | null
  updated_date: string | null
  whois_server: string | null
  dns: DNSData
  geoip: Record<string, GeoIPRecord>
  http: HTTPData | null
  ssl: SSLData | null
  ports: PortsData | null
  latency: LatencyData | null
  analysis_errors: AnalysisError[]
}

export interface ErrorDetails {
  loc?: string[]
  message?: string
  [key: string]: unknown
}

export interface ErrorPayload {
  code: string
  message: string
  details?: ErrorDetails[]
}
