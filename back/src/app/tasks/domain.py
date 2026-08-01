import asyncio
from time import perf_counter
from typing import Any

from app.core.celery_app import celery_app
from app.core.metrics import record_job
from app.services.domain import DomainService


@celery_app.task(bind=True, name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(task, domain: str) -> dict[str, Any]:
    started_at = perf_counter()
    outcome = 'failed'
    task_id = task.request.id
    try:
        result = asyncio.run(DomainService().analyze(domain, analysis_id=task_id, task_id=task_id))
        outcome = 'completed'
        return result.model_dump(mode='json')
    except asyncio.CancelledError:
        outcome = 'cancelled'
        raise
    finally:
        record_job(outcome, perf_counter() - started_at)
