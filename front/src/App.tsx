import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import { ApiError, cancelAnalysis, createAnalysis, pollAnalysis } from './api/client'
import type { AnalysisJob, AnalysisJobStatus, AnalysisProgress as AnalysisProgressItem, DomainAnalysis } from './api/types'
import AnalysisForm from './components/AnalysisForm'
import AnalysisProgress from './components/AnalysisProgress'
import AnalysisResults from './components/AnalysisResults'
import LanguageSwitcher from './components/LanguageSwitcher'
import { useI18n } from './i18n-context'
import type { Translate } from './i18n-utils'

type ViewState =
  | { status: 'idle' }
  | {
      status: 'loading'
      phase: Extract<AnalysisJobStatus, 'queued' | 'running'>
      jobId: string | null
      progress: AnalysisProgressItem[]
    }
  | { status: 'success'; analysis: DomainAnalysis }
  | { status: 'error'; error: Error }

function isAbortError(error: unknown) {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

function errorMessage(error: Error, t: Translate) {
  if (error instanceof ApiError && error.status === 429) {
    return t('rateLimitMessage', { message: error.message })
  }
  if (error instanceof ApiError && error.status === 503) {
    return t('serviceUnavailableMessage', { message: error.message })
  }

  return error.message
}

function statusMessage(view: ViewState, t: Translate) {
  if (view.status !== 'loading') {
    return t('resultsStay')
  }

  return view.phase === 'queued' ? t('waitingWorker') : t('collectingSignals')
}

function isActiveJob(job: AnalysisJob): job is AnalysisJob & { status: 'queued' | 'running' } {
  return job.status === 'queued' || job.status === 'running'
}

function App() {
  const { t } = useI18n()
  const [domain, setDomain] = useState('')
  const [view, setView] = useState<ViewState>({ status: 'idle' })
  const controllerRef = useRef<AbortController | null>(null)
  const jobIdRef = useRef<string | null>(null)
  const runTokenRef = useRef(0)

  const requestCancellation = (jobId: string) => {
    void cancelAnalysis(jobId).catch(() => undefined)
  }

  const runAnalysis = async (target: string) => {
    const runToken = runTokenRef.current + 1
    runTokenRef.current = runToken
    controllerRef.current?.abort()
    if (jobIdRef.current) {
      requestCancellation(jobIdRef.current)
    }
    jobIdRef.current = null

    const controller = new AbortController()
    controllerRef.current = controller
    setView({ status: 'loading', phase: 'queued', jobId: null, progress: [] })

    try {
      const initialJob = await createAnalysis(target)
      if (runTokenRef.current !== runToken) {
        requestCancellation(initialJob.id)
        return
      }

      jobIdRef.current = initialJob.id
      if (isActiveJob(initialJob)) {
        setView({
          status: 'loading',
          phase: initialJob.status,
          jobId: initialJob.id,
          progress: initialJob.progress,
        })
      }

      const finalJob = await pollAnalysis(
        initialJob.id,
        controller.signal,
        (job) => {
          if (runTokenRef.current !== runToken || !isActiveJob(job)) {
            return
          }
          setView({
            status: 'loading',
            phase: job.status,
            jobId: job.id,
            progress: job.progress,
          })
        },
      )

      if (runTokenRef.current !== runToken) {
        return
      }

      if (finalJob.status === 'completed') {
        if (!finalJob.result) {
          throw new ApiError(t('missingAnalysisResult'), 502, 'missing_analysis_result')
        }
        setView({ status: 'success', analysis: finalJob.result })
      } else if (finalJob.status === 'failed') {
        const error = finalJob.error
        throw new ApiError(
          error?.message ?? t('workerFailed'),
          502,
          error?.code ?? 'analysis_failed',
          error?.details,
        )
      } else {
        setView({ status: 'idle' })
      }
    } catch (error) {
      if (runTokenRef.current !== runToken || isAbortError(error)) {
        return
      }

      const normalizedError = error instanceof Error ? error : new Error(t('unexpectedFailure'))
      setView({ status: 'error', error: normalizedError })
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null
      }
      if (runTokenRef.current === runToken) {
        jobIdRef.current = null
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
    runTokenRef.current += 1
    controllerRef.current?.abort()
    controllerRef.current = null
    const jobId = jobIdRef.current
    jobIdRef.current = null
    setView({ status: 'idle' })
    if (jobId) {
      requestCancellation(jobId)
    }
  }

  const loading = view.status === 'loading'

  return (
    <main className="app-shell">
      <div className="page-width">
        <header className="app-toolbar">
          <p className="toolbar-name">{t('domainAnalyzer')}</p>
          <LanguageSwitcher />
        </header>

        <section className="search-panel" aria-label={t('domainAnalysisForm')}>
          <AnalysisForm
            domain={domain}
            loading={loading}
            onChange={handleChange}
            onCancel={handleCancel}
            onSubmit={handleSubmit}
          />
          <p className="request-status" role="status" aria-live="polite" aria-busy={loading}>
            {statusMessage(view, t)}
          </p>
        </section>

        {view.status === 'loading' && <AnalysisProgress progress={view.progress} />}

        {view.status === 'error' && (
          <section className="error-panel" role="alert">
            <div>
              <strong>{t('analysisCouldNotBeCompleted')}</strong>
              <p>{errorMessage(view.error, t)}</p>
            </div>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void runAnalysis(domain.trim())}
              disabled={!domain.trim()}
            >
              {t('tryAgain')}
            </button>
          </section>
        )}

        {view.status === 'success' && <AnalysisResults analysis={view.analysis} />}
      </div>
    </main>
  )
}

export default App
