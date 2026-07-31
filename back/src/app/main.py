from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.root import root_router
from app.core.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.TITLE,
        docs_url=config.DOCS_URL,
        openapi_url=config.OPENAPI_URL,
        redoc_url=config.REDOC_URL,
        lifespan=lifespan,
        debug=config.DEBUG,
    )

    app.include_router(root_router)

    return app
