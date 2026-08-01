from celery import Celery

from app.core.config import settings

celery_app = Celery(
    'domain_analyzer',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks.domain'],
)

celery_app.conf.update(
    accept_content=['json'],
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    result_expires=settings.CELERY_RESULT_EXPIRES_SECONDS,
    result_serializer='json',
    task_acks_late=True,
    task_default_queue='domain_analysis',
    task_reject_on_worker_lost=True,
    task_routes={'app.tasks.domain.analyze_domain_task': {'queue': 'domain_analysis'}},
    task_serializer='json',
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_track_started=True,
    timezone='UTC',
    worker_prefetch_multiplier=1,
)
