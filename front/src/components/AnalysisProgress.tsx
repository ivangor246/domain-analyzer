import type { AnalysisCheckStatus, AnalysisProgress as AnalysisProgressItem } from '../api/types'
import { useI18n, type Translate } from '../i18n'

interface AnalysisProgressProps {
  progress: AnalysisProgressItem[]
}

const checkKeys: Record<string, string> = {
  rdap: 'rdap',
  dns: 'dns',
  dns_propagation: 'dns_propagation',
  geoip: 'geoip',
  http: 'http',
  ssl: 'ssl',
  ports: 'ports',
  latency: 'latency',
}

const statusKeys: Record<AnalysisCheckStatus, string> = {
  queued: 'queued',
  running: 'running',
  successful: 'successful',
  partial: 'partial',
  failed: 'failed',
}

function checkLabel(check: string, t: Translate) {
  const key = checkKeys[check]
  return key ? t(key) : check.replaceAll('_', ' ')
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
  const { t } = useI18n()
  const completedCount = progress.filter((item) => completedStatus(item.status)).length
  const runningCount = progress.filter((item) => item.status === 'running').length
  const summary = progress.length === 0
    ? t('preparingChecks')
    : t('progressSummary', {
        completed: completedCount,
        total: progress.length,
        running: runningCount > 0 ? t('progressRunning', { count: runningCount }) : '',
      })

  return (
    <section className="progress-panel" aria-labelledby="progress-heading">
      <div className="progress-heading">
        <div>
          <p className="eyebrow">{t('liveStatus')}</p>
          <h2 id="progress-heading">{t('analysisProgress')}</h2>
        </div>
        <p className="progress-summary" role="status" aria-live="polite">
          {summary}
        </p>
      </div>

      {progress.length === 0 ? (
        <p className="progress-empty">{t('workerPreparingQueue')}</p>
      ) : (
        <ul className="progress-list">
          {progress.map((item, index) => (
            <li className="progress-item" key={`${item.check}-${index}`}>
              <span className="progress-check">{checkLabel(item.check, t)}</span>
              <span className={`progress-status progress-status-${item.status}`}>
                {t(statusKeys[item.status])}
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
