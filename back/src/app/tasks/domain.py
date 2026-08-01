import asyncio
from typing import Any

from app.core.celery_app import celery_app
from app.services.domain import DomainService


@celery_app.task(name='app.tasks.domain.analyze_domain_task')
def analyze_domain_task(domain: str) -> dict[str, Any]:
    result = asyncio.run(DomainService().analyze(domain))
    return result.model_dump(mode='json')
