import asyncio
import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import correlation_context
from app.core.metrics import record_job
from app.services.analysis_concurrency import (
    AnalysisConcurrencyBusyError,
    AnalysisConcurrencyUnavailableError,
    run_with_concurrency_limit,
)
from app.services.analysis_queue import mark_analysis_started
from app.services.domain import DomainService

logger = logging.getLogger(__name__)


def _request_id_from_task(task: Any) -> str | None:
    headers = getattr(task.request, 'headers', None)
    if not isinstance(headers, Mapping):
        return None
    request_id = headers.get('request_id')
    return request_id if isinstance(request_id, str) else None


@celery_app.task(bind=True, name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(task, domain: str) -> dict[str, Any]:
    task_id = task.request.id
    request_id = _request_id_from_task(task)
    with correlation_context(request_id=request_id, analysis_id=task_id, task_id=task_id):
        started_at = perf_counter()
        outcome = 'failed'
        logger.info('analysis task started', extra={'domain': domain})
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
            duration_seconds = perf_counter() - started_at
            record_job(outcome, duration_seconds)
            logger.info(
                'analysis task finished',
                extra={
                    'domain': domain,
                    'job_status': outcome,
                    'job_duration_ms': round(duration_seconds * 1000, 2),
                },
            )
