import type { ChangeEvent, FormEvent } from 'react'

interface AnalysisFormProps {
  domain: string
  loading: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onCancel: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

function AnalysisForm({ domain, loading, onChange, onCancel, onSubmit }: AnalysisFormProps) {
  return (
    <form className="analysis-form" onSubmit={onSubmit}>
      <label htmlFor="domain-input">Domain name</label>
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
            Cancel
          </button>
        ) : (
          <button type="submit" className="button button-primary" disabled={!domain.trim()}>
            Analyze domain
          </button>
        )}
      </div>
      <p id="domain-help" className="form-help">
        Enter a public domain. The backend validates the target and returns partial results when a provider is
        unavailable.
      </p>
    </form>
  )
}

export default AnalysisForm
