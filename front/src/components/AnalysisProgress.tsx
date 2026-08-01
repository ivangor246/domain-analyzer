import type { AnalysisCheckStatus, AnalysisProgress as AnalysisProgressItem } from '../api/types'

interface AnalysisProgressProps {
  progress: AnalysisProgressItem[]
}

const checkLabels: Record<string, string> = {
  rdap: 'RDAP registration',
  dns: 'DNS records',
  dns_propagation: 'DNS propagation',
  geoip: 'GeoIP and ASN',
  http: 'HTTP and HTTPS',
  ssl: 'TLS certificate',
  ports: 'Port scan',
  latency: 'TCP latency',
}

const statusLabels: Record<AnalysisCheckStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  successful: 'Successful',
  partial: 'Partial',
  failed: 'Failed',
}

function checkLabel(check: string) {
  return checkLabels[check] ?? check.replaceAll('_', ' ')
}

function formatDuration(durationMs: number | null) {
  if (durationMs === null) {
    return '—'
  }
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`
  }
  return `${(durationMs / 1000).toFixed(1)} s`
}

function completedStatus(status: AnalysisCheckStatus) {
  return status === 'successful' || status === 'partial' || status === 'failed'
}

function AnalysisProgress({ progress }: AnalysisProgressProps) {
  const completedCount = progress.filter((item) => completedStatus(item.status)).length
  const runningCount = progress.filter((item) => item.status === 'running').length
  const summary = progress.length === 0
    ? 'Preparing checks…'
    : `${completedCount} of ${progress.length} checks complete${runningCount > 0 ? `, ${runningCount} running` : ''}.`

  return (
    <section className="progress-panel" aria-labelledby="progress-heading">
      <div className="progress-heading">
        <div>
          <p className="eyebrow">Live status</p>
          <h2 id="progress-heading">Analysis progress</h2>
        </div>
        <p className="progress-summary" role="status" aria-live="polite">
          {summary}
        </p>
      </div>

      {progress.length === 0 ? (
        <p className="progress-empty">The worker is preparing the analysis queue.</p>
      ) : (
        <ul className="progress-list">
          {progress.map((item, index) => (
            <li className="progress-item" key={`${item.check}-${index}`}>
              <span className="progress-check">{checkLabel(item.check)}</span>
              <span className={`progress-status progress-status-${item.status}`}>
                {statusLabels[item.status]}
              </span>
              <span className="progress-duration">{formatDuration(item.duration_ms)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default AnalysisProgress
