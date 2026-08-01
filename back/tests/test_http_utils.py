import unittest
from unittest.mock import AsyncMock

import httpx

from app.utils.http import (
    ResponseTooLargeError,
    is_retryable_http_error,
    parse_json,
    read_limited_response,
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
        self.assertFalse(is_retryable_http_error(client_error))
        self.assertFalse(is_retryable_http_error(ValueError('invalid payload')))


if __name__ == '__main__':
    unittest.main()
