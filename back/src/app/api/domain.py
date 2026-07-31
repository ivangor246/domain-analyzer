from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import DomainValidationError, RDAPError
from app.schemas.domain import DomainSchema
from app.services.domain import DomainService

domain_router = APIRouter(prefix='/domain', tags=['domain'])

service = DomainService()


@domain_router.get('')
async def analyze_domain(
    d: str = Query(..., description='Target domain'),
) -> DomainSchema:

    try:
        return await service.analyze(domain=d)
    except DomainValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RDAPError as e:
        raise HTTPException(status_code=502, detail=str(e))
