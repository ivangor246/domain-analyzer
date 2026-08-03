import type { DomainAnalysis } from '../api/types'
import { useI18n, type Translate } from '../i18n'
import { getSecuritySummary, type SecuritySummary as SecuritySummaryData } from '../utils/security'

interface SecuritySummaryProps {
  analysis: DomainAnalysis
}

function scoreTone(score: number | null) {
  if (score === null) {
    return 'neutral'
  }
  if (score >= 80) {
    return 'good'
  }
  if (score >= 50) {
    return 'warning'
  }
  return 'critical'
}

function scoreLabel(score: number | null, t: Translate) {
  return score === null ? t('notAssessed') : `${score}/100`
}

function localizedFindingText(
  finding: SecuritySummaryData['findings'][number],
  t: Translate,
): { title: string; recommendation: string } {
  const days = finding.title.match(/(\d+)/)?.[1] ?? ''
  const titleKey = `finding.${finding.id}.title`
  const recommendationKey = `finding.${finding.id}.recommendation`
  const title = t(titleKey, { days })
  const recommendation = t(recommendationKey)

  return {
    title: title === titleKey ? finding.title : title,
    recommendation: recommendation === recommendationKey ? finding.recommendation : recommendation,
  }
}

function SecurityFindingList({ summary }: { summary: SecuritySummaryData }) {
  const { t } = useI18n()

  if (summary.findings.length === 0) {
    return <p className="security-empty">{t('noActionableSignals')}</p>
  }

  return (
    <ul className="security-findings">
      {summary.findings.map((finding) => {
        const text = localizedFindingText(finding, t)

        return (
          <li className="security-finding" key={finding.id}>
            <span className={`severity-badge severity-${finding.severity}`}>
              {t(`severity${finding.severity[0].toUpperCase()}${finding.severity.slice(1)}`)}
            </span>
            <div>
              <strong>{text.title}</strong>
              <p>{text.recommendation}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function SecuritySummary({ analysis }: SecuritySummaryProps) {
  const { t } = useI18n()
  const summary = getSecuritySummary(analysis)
  const tone = scoreTone(summary.score)
  const score = scoreLabel(summary.score, t)

  return (
    <section className="security-summary" aria-labelledby="security-signals-heading">
      <div className="security-summary-heading">
        <h3 id="security-signals-heading">{t('securitySignals')}</h3>
      </div>
      <details className="result-details">
        <summary>{t('showResults')}</summary>
        <div className="security-summary-content">
          <div className="security-score-row">
            <span className={`security-score score-${tone}`} aria-label={t('securityScore', { score })}>
              {score}
            </span>
          </div>
          <p className="security-summary-note">
            {summary.assessedSignals > 0
              ? t('securityNoteScored', { count: summary.assessedSignals })
              : t('securityNoteUnavailable')}
          </p>
          <SecurityFindingList summary={summary} />
        </div>
      </details>
    </section>
  )
}

export default SecuritySummary
