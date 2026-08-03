import type { ChangeEvent, FormEvent } from 'react'

import { useI18n } from '../i18n-context'

interface AnalysisFormProps {
  domain: string
  loading: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onCancel: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

function AnalysisForm({ domain, loading, onChange, onCancel, onSubmit }: AnalysisFormProps) {
  const { t } = useI18n()

  return (
    <form className="analysis-form" onSubmit={onSubmit}>
      <label htmlFor="domain-input">{t('domainName')}</label>
      <div className="form-row">
        <input
          id="domain-input"
          name="domain"
          type="text"
          value={domain}
          onChange={onChange}
          placeholder="example.com"
          autoComplete="url"
          spellCheck="false"
          required
          aria-describedby="domain-help"
          disabled={loading}
        />
        {loading ? (
          <button type="button" className="button button-secondary" onClick={onCancel}>
            {t('cancel')}
          </button>
        ) : (
          <button type="submit" className="button button-primary" disabled={!domain.trim()}>
            {t('analyzeDomain')}
          </button>
        )}
      </div>
      <p id="domain-help" className="form-help">
        {t('domainHelp')}
      </p>
    </form>
  )
}

export default AnalysisForm
