from fastapi import APIRouter

from .domain import domain_router

ROUTERS: list[APIRouter] = [
    domain_router,
]

root_router = APIRouter(prefix='/api')

for router in ROUTERS:
    root_router.include_router(router)
