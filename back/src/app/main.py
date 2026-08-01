from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable
from logging import getLogger
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    app_error_handler,
    http_error_handler,
    request_validation_error_handler,
    unexpected_error_handler,
)
from app.api.root import root_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging, request_id_context
from app.core.rate_limit import RateLimiter

logger = getLogger(__name__)

_RATE_LIMITED_PATHS = {
    ('GET', '/api/domain'),
    ('POST', '/api/analyses'),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    configure_logging(debug=settings.DEV_MODE)

    app = FastAPI(
        title=settings.TITLE,
        version='0.1.0',
        description=(
            'Asynchronous domain analysis API. Results may be partial when an external provider is unavailable.'
        ),
        docs_url=settings.DOCS_URL,
        openapi_url=settings.OPENAPI_URL,
        redoc_url=settings.REDOC_URL,
        lifespan=lifespan,
        debug=settings.DEV_MODE,
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=['GET', 'POST'],
        allow_headers=['Accept', 'Content-Type', 'Idempotency-Key'],
    )

    rate_limit_enabled = settings.RATE_LIMIT_ENABLED
    rate_limit_requests = settings.RATE_LIMIT_REQUESTS
    rate_limiter = RateLimiter(
        max_requests=rate_limit_requests,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )

    @app.middleware('http')
    async def enforce_rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if rate_limit_enabled and (request.method, request.url.path) in _RATE_LIMITED_PATHS:
            client_key = request.client.host if request.client else 'unknown'
            decision = await rate_limiter.check(client_key)
            rate_headers = {
                'X-RateLimit-Limit': str(rate_limit_requests),
                'X-RateLimit-Remaining': str(decision.remaining),
            }
            if not decision.allowed:
                rate_headers['Retry-After'] = str(decision.retry_after)
                return JSONResponse(
                    status_code=429,
                    content={
                        'code': 'rate_limit_exceeded',
                        'message': 'Too many requests. Try again later.',
                    },
                    headers=rate_headers,
                )

            response = await call_next(request)
            for name, value in rate_headers.items():
                response.headers[name] = value
            return response

        return await call_next(request)

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
