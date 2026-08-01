import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.utils.http import (
    ResponseTooLargeError,
    is_retryable_http_error,
    parse_json,
    read_limited_response,
    retry_after_seconds,
    run_with_retries,
)


class HTTPUtilsTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_limited_response_returns_content(self):
        response = httpx.Response(200, content=b'{"status":"ok"}')

        content = await read_limited_response(response, max_bytes=100)

        self.assertEqual(content, b'{"status":"ok"}')
        self.assertEqual(parse_json(content), {'status': 'ok'})

    async def test_read_limited_response_rejects_large_content_length(self):
        response = httpx.Response(200, headers={'content-length': '10'}, content=b'1234567890')

        with self.assertRaises(ResponseTooLargeError):
            await read_limited_response(response, max_bytes=9)

    async def test_read_limited_response_rejects_large_stream(self):
        response = httpx.Response(200, content=b'1234567890')
        response.headers.pop('content-length')

        with self.assertRaises(ResponseTooLargeError):
            await read_limited_response(response, max_bytes=9)

    async def test_run_with_retries_retries_transient_failure(self):
        operation = AsyncMock(side_effect=[httpx.ConnectError('temporary failure'), 'ok'])

        result = await run_with_retries(
            operation,
            retries=1,
            should_retry=lambda exc: isinstance(exc, httpx.NetworkError),
            backoff_seconds=0,
        )

        self.assertEqual(result, 'ok')
        self.assertEqual(operation.await_count, 2)

    async def test_run_with_retries_retries_timeout(self):
        operation = AsyncMock(side_effect=[httpx.ReadTimeout('temporary timeout'), 'ok'])

        result = await run_with_retries(
            operation,
            retries=1,
            should_retry=is_retryable_http_error,
            backoff_seconds=0,
        )

        self.assertEqual(result, 'ok')
        self.assertEqual(operation.await_count, 2)

    async def test_run_with_retries_propagates_cancellation_without_retrying(self):
        operation = AsyncMock(side_effect=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await run_with_retries(
                operation,
                retries=3,
                should_retry=lambda _exc: True,
                backoff_seconds=0,
            )

        operation.assert_awaited_once()

    async def test_run_with_retries_honors_retry_after_and_adds_jitter(self):
        request = httpx.Request('GET', 'https://provider.example')
        response = httpx.Response(429, headers={'Retry-After': '2'}, request=request)
        operation = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError('rate limited', request=request, response=response),
                'ok',
            ]
        )

        with (
            patch('app.utils.http.random.uniform', return_value=0.25),
            patch('app.utils.http.asyncio.sleep', new=AsyncMock()) as sleep,
        ):
            result = await run_with_retries(
                operation,
                retries=1,
                should_retry=is_retryable_http_error,
                backoff_seconds=0.1,
                jitter_seconds=0.25,
                retry_after=retry_after_seconds,
                max_delay_seconds=10,
            )

        self.assertEqual(result, 'ok')
        sleep.assert_awaited_once_with(2.25)

    async def test_run_with_retries_caps_provider_delay(self):
        request = httpx.Request('GET', 'https://provider.example')
        response = httpx.Response(503, headers={'Retry-After': '120'}, request=request)
        operation = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError('unavailable', request=request, response=response),
                'ok',
            ]
        )

        with patch('app.utils.http.asyncio.sleep', new=AsyncMock()) as sleep:
            await run_with_retries(
                operation,
                retries=1,
                should_retry=is_retryable_http_error,
                backoff_seconds=0,
                retry_after=retry_after_seconds,
                max_delay_seconds=3,
            )

        sleep.assert_awaited_once_with(3)

    def test_is_retryable_http_error_distinguishes_status_codes(self):
        request = httpx.Request('GET', 'https://example.com')
        server_error = httpx.HTTPStatusError(
            'server error',
            request=request,
            response=httpx.Response(503, request=request),
        )
        client_error = httpx.HTTPStatusError(
            'client error',
            request=request,
            response=httpx.Response(400, request=request),
        )

        self.assertTrue(is_retryable_http_error(server_error))
        self.assertTrue(
            is_retryable_http_error(
                httpx.HTTPStatusError(
                    'rate limited',
                    request=request,
                    response=httpx.Response(429, request=request),
                )
            )
        )
        self.assertFalse(is_retryable_http_error(client_error))
        self.assertFalse(is_retryable_http_error(ValueError('invalid payload')))

    def test_retry_after_supports_seconds_and_invalid_values(self):
        request = httpx.Request('GET', 'https://example.com')
        seconds_error = httpx.HTTPStatusError(
            'rate limited',
            request=request,
            response=httpx.Response(429, headers={'Retry-After': '2.5'}, request=request),
        )
        invalid_error = httpx.HTTPStatusError(
            'rate limited',
            request=request,
            response=httpx.Response(429, headers={'Retry-After': 'later'}, request=request),
        )

        self.assertEqual(retry_after_seconds(seconds_error), 2.5)
        self.assertIsNone(retry_after_seconds(invalid_error))
        self.assertIsNone(retry_after_seconds(ValueError('not an HTTP error')))


if __name__ == '__main__':
    unittest.main()
