import type { DomainAnalysis } from '../api/types'
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

function scoreLabel(score: number | null) {
  return score === null ? 'Not assessed' : `${score}/100`
}

function SecurityFindingList({ summary }: { summary: SecuritySummaryData }) {
  if (summary.findings.length === 0) {
    return <p className="security-empty">No actionable signals were found in the collected responses.</p>
  }

  return (
    <ul className="security-findings">
      {summary.findings.map((finding) => (
        <li className="security-finding" key={finding.id}>
          <span className={`severity-badge severity-${finding.severity}`}>{finding.severity}</span>
          <div>
            <strong>{finding.title}</strong>
            <p>{finding.recommendation}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

function SecuritySummary({ analysis }: SecuritySummaryProps) {
  const summary = getSecuritySummary(analysis)
  const tone = scoreTone(summary.score)

  return (
    <section className="security-summary" aria-labelledby="security-signals-heading">
      <div className="security-summary-heading">
        <div>
          <p className="eyebrow">Heuristic review</p>
          <h3 id="security-signals-heading">Security signals</h3>
        </div>
        <span className={`security-score score-${tone}`} aria-label={`Security signal score: ${scoreLabel(summary.score)}`}>
          {scoreLabel(summary.score)}
        </span>
      </div>
      <p className="security-summary-note">
        This is a transparent signal check, not a complete security audit.{' '}
        {summary.assessedSignals > 0
          ? `The score uses ${summary.assessedSignals} collected signal(s).`
          : 'The available data was not sufficient to calculate a score.'}
      </p>
      <SecurityFindingList summary={summary} />
    </section>
  )
}

export default SecuritySummary
