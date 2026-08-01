import asyncio
from typing import Any

from app.core.celery_app import celery_app
from app.services.domain import DomainService


@celery_app.task(bind=True, name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(task, domain: str) -> dict[str, Any]:
    task_id = task.request.id
    result = asyncio.run(DomainService().analyze(domain, analysis_id=task_id, task_id=task_id))
    return result.model_dump(mode='json')
