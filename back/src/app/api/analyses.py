from fastapi import APIRouter, Header, Path, status

from app.core.logging_config import request_id_context
from app.schemas.analysis import AnalysisCreateSchema, AnalysisJobSchema
from app.schemas.error import ErrorSchema
from app.services.analysis_jobs import AnalysisJobService

analysis_router = APIRouter(prefix='/analyses', tags=['analysis'])

service = AnalysisJobService()


@analysis_router.post(
    '',
    response_model=AnalysisJobSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary='Queue a domain analysis',
    description='Validate a domain and enqueue its analysis in the Celery worker.',
    responses={
        400: {'model': ErrorSchema, 'description': 'The domain is invalid.'},
        409: {'model': ErrorSchema, 'description': 'The idempotency key belongs to another domain.'},
        422: {'model': ErrorSchema, 'description': 'The request body is invalid.'},
        429: {'model': ErrorSchema, 'description': 'The client exceeded the configured request rate.'},
        503: {'model': ErrorSchema, 'description': 'The analysis queue is unavailable.'},
    },
)
async def create_analysis(
    payload: AnalysisCreateSchema,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key', max_length=128),
) -> AnalysisJobSchema:
    return await service.create(
        domain=payload.domain,
        idempotency_key=idempotency_key,
        request_id=request_id_context.get(),
    )


@analysis_router.get(
    '/{analysis_id}',
    response_model=AnalysisJobSchema,
    summary='Get analysis status',
    description='Return the current state and result of a queued domain analysis.',
    responses={
        404: {'model': ErrorSchema, 'description': 'The analysis job does not exist or has expired.'},
        503: {'model': ErrorSchema, 'description': 'The analysis queue is unavailable.'},
    },
)
async def get_analysis(
    analysis_id: str = Path(..., pattern=r'^[0-9a-f]{32}$', description='Analysis identifier'),
) -> AnalysisJobSchema:
    return await service.get(analysis_id)


@analysis_router.post(
    '/{analysis_id}/cancel',
    response_model=AnalysisJobSchema,
    summary='Cancel analysis',
    description='Request cancellation of a queued or running domain analysis.',
    responses={
        404: {'model': ErrorSchema, 'description': 'The analysis job does not exist or has expired.'},
        503: {'model': ErrorSchema, 'description': 'The analysis queue is unavailable.'},
    },
)
async def cancel_analysis(
    analysis_id: str = Path(..., pattern=r'^[0-9a-f]{32}$', description='Analysis identifier'),
) -> AnalysisJobSchema:
    return await service.cancel(analysis_id)
