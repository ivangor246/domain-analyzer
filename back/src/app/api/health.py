from fastapi import APIRouter

from app.schemas.health import HealthSchema

health_router = APIRouter(prefix='/health', tags=['health'])


@health_router.get('', response_model=HealthSchema, summary='Check service health')
async def health_check() -> HealthSchema:
    return HealthSchema()
