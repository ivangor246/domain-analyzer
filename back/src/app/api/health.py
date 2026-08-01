from fastapi import APIRouter

from app.schemas.health import HealthSchema

health_router = APIRouter(prefix='/health', tags=['health'])


@health_router.get(
    '',
    response_model=HealthSchema,
    summary='Check service health',
    description='Return process health without contacting domain-analysis providers.',
)
async def health_check() -> HealthSchema:
    return HealthSchema()
