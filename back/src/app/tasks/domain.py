import asyncio
import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import correlation_context
from app.core.metrics import record_job
from app.schemas.analysis import ANALYSIS_CHECKS
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


class TaskProgressReporter:
    def __init__(self, task: Any) -> None:
        self.task = task
        self._lock = asyncio.Lock()
        self._progress: dict[str, dict[str, object]] = {
            check: {'check': check, 'status': 'queued', 'duration_ms': None} for check in ANALYSIS_CHECKS
        }

    def snapshot(self) -> list[dict[str, object]]:
        return [dict(self._progress[check]) for check in ANALYSIS_CHECKS]

    async def _publish(self, progress: list[dict[str, object]]) -> None:
        try:
            await asyncio.to_thread(
                self.task.update_state,
                state='PROGRESS',
                meta={'progress': progress},
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning('analysis progress publication failed')

    async def publish_initial(self) -> None:
        await self._publish(self.snapshot())

    async def report(self, check: str, status: str, duration_ms: float | None = None) -> None:
        async with self._lock:
            updated = {'check': check, 'status': status, 'duration_ms': duration_ms}
            if self._progress.get(check) == updated:
                return
            self._progress[check] = updated
            await self._publish(self.snapshot())


@celery_app.task(bind=True, name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(task, domain: str) -> dict[str, Any]:
    task_id = task.request.id
    request_id = _request_id_from_task(task)
    with correlation_context(request_id=request_id, analysis_id=task_id, task_id=task_id):
        started_at = perf_counter()
        outcome = 'failed'
        logger.info('analysis task started', extra={'domain': domain})
        try:

            async def run_analysis() -> tuple[dict[str, Any], list[dict[str, object]]]:
                reporter = TaskProgressReporter(task)
                await reporter.publish_initial()
                result = await run_with_concurrency_limit(
                    task_id,
                    lambda: DomainService().analyze(
                        domain,
                        analysis_id=task_id,
                        task_id=task_id,
                        progress_callback=reporter.report,
                    ),
                    on_acquired=lambda: mark_analysis_started(task_id),
                )
                return result.model_dump(mode='json'), reporter.snapshot()

            result, progress = asyncio.run(run_analysis())
            outcome = 'completed'
            return {'analysis': result, 'progress': progress}
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
