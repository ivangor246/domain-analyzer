from fastapi import APIRouter

from .hi import hi_router

ROUTERS: list[APIRouter] = [
    hi_router,
]

root_router = APIRouter(prefix='/api')

for router in ROUTERS:
    root_router.include_router(router)
