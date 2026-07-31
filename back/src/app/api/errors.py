from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.schemas.error import ErrorSchema


def _error_response(status_code: int, error: ErrorSchema) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error.model_dump(exclude_none=True))


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        error=ErrorSchema(code=exc.code, message=str(exc)),
    )


async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else 'HTTP request failed.'
    return _error_response(
        status_code=exc.status_code,
        error=ErrorSchema(code='http_error', message=message),
    )


async def request_validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    details: list[dict[str, Any]] = [
        {
            'loc': [str(part) for part in error.get('loc', ())],
            'message': error.get('msg', 'Invalid value'),
        }
        for error in exc.errors()
    ]
    return _error_response(
        status_code=422,
        error=ErrorSchema(
            code='request_validation_error',
            message='Request validation failed.',
            details=details,
        ),
    )


async def unexpected_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return _error_response(
        status_code=500,
        error=ErrorSchema(code='internal_error', message='An unexpected error occurred.'),
    )
