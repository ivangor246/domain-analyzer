from fastapi import APIRouter, Query

from app.schemas.domain import DomainSchema
from app.services.domain import DomainService

domain_router = APIRouter(prefix='/domain', tags=['domain'])

service = DomainService()


@domain_router.get('')
async def analyze_domain(
    d: str = Query(..., description='Target domain'),
) -> DomainSchema:
    return await service.analyze(domain=d)
