import asyncio
from collections.abc import Awaitable, Callable
import json
from typing import TypeVar

import httpx

T = TypeVar('T')


class ResponseTooLargeError(ValueError):
    pass


async def read_limited_response(response: httpx.Response, max_bytes: int) -> bytes:
    content_length = response.headers.get('content-length')
    if content_length:
        try:
            content_length_value = int(content_length)
        except ValueError:
            content_length_value = None
        if content_length_value is not None and content_length_value > max_bytes:
            raise ResponseTooLargeError('Upstream response exceeds the configured size limit.')

    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLargeError('Upstream response exceeds the configured size limit.')
        chunks.append(chunk)
    return b''.join(chunks)


async def run_with_retries(
    operation: Callable[[], Awaitable[T]],
    retries: int,
    should_retry: Callable[[Exception], bool],
    backoff_seconds: float,
) -> T:
    for attempt in range(retries + 1):
        try:
            return await operation()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if attempt >= retries or not should_retry(exc):
                raise
            await asyncio.sleep(backoff_seconds * (2**attempt))

    raise RuntimeError('Retry loop completed without a result.')


def is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response is not None and exc.response.status_code >= 500
    return False


def parse_json(content: bytes) -> object:
    return json.loads(content)
