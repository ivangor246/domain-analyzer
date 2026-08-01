from fastapi import APIRouter

from .analyses import analysis_router
from .domain import domain_router
from .health import health_router

ROUTERS: list[APIRouter] = [
    health_router,
    domain_router,
    analysis_router,
]

root_router = APIRouter(prefix='/api')

for router in ROUTERS:
    root_router.include_router(router)
