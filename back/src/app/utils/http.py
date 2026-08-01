import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import random
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
    jitter_seconds: float = 0,
    retry_after: Callable[[Exception], float | None] | None = None,
    max_delay_seconds: float | None = None,
) -> T:
    for attempt in range(retries + 1):
        try:
            return await operation()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if attempt >= retries or not should_retry(exc):
                raise
            delay = backoff_seconds * (2**attempt)
            if retry_after is not None:
                delay = max(delay, retry_after(exc) or 0)
            if jitter_seconds > 0:
                delay += random.uniform(0, jitter_seconds)
            if max_delay_seconds is not None:
                delay = min(delay, max_delay_seconds)
            await asyncio.sleep(max(0, delay))

    raise RuntimeError('Retry loop completed without a result.')


def is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response is not None and (exc.response.status_code == 429 or exc.response.status_code >= 500)
    return False


def retry_after_seconds(exc: Exception) -> float | None:
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response is None:
        return None

    value = exc.response.headers.get('retry-after')
    if not value:
        return None

    try:
        return max(0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def parse_json(content: bytes) -> object:
    return json.loads(content)
