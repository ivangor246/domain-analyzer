from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable
from logging import getLogger
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    app_error_handler,
    http_error_handler,
    request_validation_error_handler,
    unexpected_error_handler,
)
from app.api.root import root_router
from app.core.config import config
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging, request_id_context

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    configure_logging(debug=config.DEBUG)

    app = FastAPI(
        title=config.TITLE,
        docs_url=config.DOCS_URL,
        openapi_url=config.OPENAPI_URL,
        redoc_url=config.REDOC_URL,
        lifespan=lifespan,
        debug=config.DEBUG,
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    @app.middleware('http')
    async def log_request(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = uuid4().hex
        token = request_id_context.set(request_id)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                'request failed',
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': 500,
                    'duration_ms': round((perf_counter() - started_at) * 1000, 2),
                },
            )
            raise
        else:
            response.headers['X-Request-ID'] = request_id
            logger.info(
                'request completed',
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration_ms': round((perf_counter() - started_at) * 1000, 2),
                },
            )
            return response
        finally:
            request_id_context.reset(token)

    app.include_router(root_router)

    return app
