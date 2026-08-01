from fastapi import APIRouter, Query

from app.core.config import settings
from app.schemas.error import ErrorSchema
from app.schemas.domain import DomainSchema
from app.services.domain import DomainService

domain_router = APIRouter(prefix='/domain', tags=['domain'])

service = DomainService()


@domain_router.get(
    '',
    response_model=DomainSchema,
    summary='Analyze a domain',
    description=(
        'Run the available RDAP, DNS, GeoIP, HTTP, TLS, port, and latency checks. '
        'Individual upstream failures are returned in analysis_errors when possible.'
    ),
    response_description='Structured domain analysis with optional partial results.',
    responses={
        400: {'model': ErrorSchema, 'description': 'The domain is invalid or the target is not allowed.'},
        422: {'model': ErrorSchema, 'description': 'The request query is invalid.'},
        429: {'model': ErrorSchema, 'description': 'The client exceeded the configured request rate.'},
        502: {'model': ErrorSchema, 'description': 'An upstream service is unavailable.'},
    },
)
async def analyze_domain(
    d: str = Query(..., min_length=1, max_length=settings.MAX_DOMAIN_LENGTH, description='Domain to analyze'),
) -> DomainSchema:
    return await service.analyze(domain=d)
