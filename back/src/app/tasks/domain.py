import asyncio
from time import perf_counter
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.metrics import record_job
from app.services.analysis_concurrency import (
    AnalysisConcurrencyBusyError,
    AnalysisConcurrencyUnavailableError,
    run_with_concurrency_limit,
)
from app.services.analysis_queue import mark_analysis_started
from app.services.domain import DomainService


@celery_app.task(bind=True, name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(task, domain: str) -> dict[str, Any]:
    started_at = perf_counter()
    outcome = 'failed'
    task_id = task.request.id
    try:
        result = asyncio.run(
            run_with_concurrency_limit(
                task_id,
                lambda: DomainService().analyze(domain, analysis_id=task_id, task_id=task_id),
                on_acquired=lambda: mark_analysis_started(task_id),
            )
        )
        outcome = 'completed'
        return result.model_dump(mode='json')
    except (AnalysisConcurrencyBusyError, AnalysisConcurrencyUnavailableError) as exc:
        outcome = 'retry'
        raise task.retry(
            exc=exc,
            countdown=settings.ANALYSIS_CONCURRENCY_RETRY_SECONDS,
            max_retries=settings.ANALYSIS_CONCURRENCY_MAX_RETRIES,
        ) from exc
    except asyncio.CancelledError:
        outcome = 'cancelled'
        raise
    finally:
        record_job(outcome, perf_counter() - started_at)
