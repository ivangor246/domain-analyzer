from fastapi import APIRouter, Response, status

from app.schemas.health import HealthSchema, ReadinessSchema
from app.services.health import check_dependencies

health_router = APIRouter(prefix='/health', tags=['health'])


@health_router.get(
    '',
    response_model=HealthSchema,
    summary='Check service health',
    description='Return process health without contacting domain-analysis providers.',
)
async def health_check() -> HealthSchema:
    return HealthSchema()


@health_router.get(
    '/ready',
    response_model=ReadinessSchema,
    responses={503: {'model': ReadinessSchema, 'description': 'A required service dependency is unavailable.'}},
    summary='Check service readiness',
    description='Check Redis and at least one responsive Celery worker without contacting analysis providers.',
)
async def readiness_check(response: Response) -> ReadinessSchema:
    dependencies = await check_dependencies()
    checks = {name: 'ok' if available else 'unavailable' for name, available in dependencies.items()}
    ready = all(dependencies.values())

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessSchema(status='ready' if ready else 'not_ready', checks=checks)
