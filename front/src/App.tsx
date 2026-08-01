import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import { analyzeDomain, ApiError } from './api/client'
import type { DomainAnalysis } from './api/types'
import AnalysisForm from './components/AnalysisForm'
import AnalysisResults from './components/AnalysisResults'

type ViewState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; analysis: DomainAnalysis }
  | { status: 'error'; error: Error }

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function errorMessage(error: Error) {
  if (error instanceof ApiError && error.status === 429) {
    return `${error.message} The rate limit will reset shortly.`
  }

  return error.message
}

function App() {
  const [domain, setDomain] = useState('')
  const [view, setView] = useState<ViewState>({ status: 'idle' })
  const controllerRef = useRef<AbortController | null>(null)

  const runAnalysis = async (target: string) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setView({ status: 'loading' })

    try {
      const analysis = await analyzeDomain(target, controller.signal)
      setView({ status: 'success', analysis })
    } catch (error) {
      if (isAbortError(error)) {
        return
      }

      const normalizedError = error instanceof Error ? error : new Error('The analysis failed unexpectedly.')
      setView({ status: 'error', error: normalizedError })
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null
      }
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const target = domain.trim()
    if (target) {
      void runAnalysis(target)
    }
  }

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    setDomain(event.target.value)
  }

  const handleCancel = () => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setView({ status: 'idle' })
  }

  const loading = view.status === 'loading'

  return (
    <main className="app-shell">
      <div className="page-width">
        <section className="hero" aria-labelledby="app-title">
          <p className="eyebrow">Network intelligence</p>
          <h1 id="app-title">Domain Analyzer</h1>
          <p className="hero-copy">Inspect the public footprint of a domain in one clear report.</p>
        </section>

        <section className="search-panel" aria-label="Domain analysis form">
          <AnalysisForm
            domain={domain}
            loading={loading}
            onChange={handleChange}
            onCancel={handleCancel}
            onSubmit={handleSubmit}
          />
          <p className="request-status" role="status" aria-live="polite" aria-busy={loading}>
            {loading ? 'Collecting public domain signals…' : 'Results stay in your browser until you analyze another domain.'}
          </p>
        </section>

        {view.status === 'error' && (
          <section className="error-panel" role="alert">
            <div>
              <strong>Analysis could not be completed</strong>
              <p>{errorMessage(view.error)}</p>
            </div>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void runAnalysis(domain.trim())}
              disabled={!domain.trim()}
            >
              Try again
            </button>
          </section>
        )}

        {view.status === 'success' && <AnalysisResults analysis={view.analysis} />}
      </div>
    </main>
  )
}

export default App
