import type { components } from './generated'

type Schemas = components['schemas']

type RequiredSchema<T> = T extends null | undefined
  ? T
  : T extends readonly (infer Item)[]
    ? Array<RequiredSchema<Item>>
    : T extends object
      ? { [Key in keyof T]-?: RequiredSchema<Exclude<T[Key], undefined>> }
      : T

export type AnalysisError = RequiredSchema<Schemas['AnalysisError']>

export type AnalysisMetadataStatus = Schemas['AnalysisCheckMetadata']['status']

export type AnalysisCheckMetadata = RequiredSchema<Schemas['AnalysisCheckMetadata']>

export type AnalysisMetadata = RequiredSchema<Schemas['AnalysisMetadata']>

export type AnalysisCheckStatus = Schemas['AnalysisCheckStatus']

export type AnalysisProgress = RequiredSchema<Schemas['AnalysisProgressSchema']>

export type AnalysisCreate = RequiredSchema<Schemas['AnalysisCreateSchema']>

export type MXRecord = RequiredSchema<Schemas['MXRecord']>

export type SOARecord = RequiredSchema<Schemas['SOARecord']>

export type CAARecord = RequiredSchema<Schemas['CAARecord']>

export type PropagationServer = RequiredSchema<Schemas['PropagationServerSchema']>

export type Propagation = RequiredSchema<Schemas['PropagationSchema']>

export type DNSData = RequiredSchema<Schemas['DNSSchema']>

export type GeoIPRecord = RequiredSchema<Schemas['GeoIPRecord']>

export type HTTPProbeResult = RequiredSchema<Schemas['HTTPProbeResult']>

export type HTTPData = RequiredSchema<Schemas['HTTPSchema']>

export type SSLCertificate = RequiredSchema<Schemas['SSLCertificate']>

export type SSLData = RequiredSchema<Schemas['SSLSchema']>

export type PortResult = RequiredSchema<Schemas['PortResult']>

export type PortsData = RequiredSchema<Schemas['PortsSchema']>

export type LatencyResult = RequiredSchema<Schemas['LatencyResult']>

export type LatencyData = RequiredSchema<Schemas['LatencySchema']>

export type DomainAnalysis = RequiredSchema<Omit<Schemas['DomainSchema'], 'metadata'>> & {
  metadata?: AnalysisMetadata | null
}

export type AnalysisJobStatus = Schemas['AnalysisStatus']

type GeneratedAnalysisJob = RequiredSchema<Omit<Schemas['AnalysisJobSchema'], 'result' | 'error' | 'progress'>>

export interface AnalysisJob extends GeneratedAnalysisJob {
  result: DomainAnalysis | null
  error: ErrorPayload | null
  progress: AnalysisProgress[]
}

export interface ErrorDetails {
  loc?: string[]
  message?: string
  [key: string]: unknown
}

export type ErrorPayload = Omit<Schemas['ErrorSchema'], 'details'> & {
  details?: ErrorDetails[] | null
}
