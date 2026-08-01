import unittest
from unittest.mock import AsyncMock

from app.services.analysis_concurrency import (
    AnalysisConcurrencyUnavailableError,
    RedisAnalysisConcurrencyLimiter,
    run_with_concurrency_limit,
)


class FakeRedis:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return next(self.responses)


class FailingRedis:
    async def eval(self, *_args):
        raise ConnectionError('Redis unavailable')


class AnalysisConcurrencyLimiterTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_acquires_and_releases_redis_lease(self) -> None:
        client = FakeRedis([1, 1])
        limiter = RedisAnalysisConcurrencyLimiter(max_concurrency=2, lease_seconds=180)
        limiter._client = client

        self.assertTrue(await limiter.acquire('task-1'))
        await limiter.release('task-1')

        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][1], 1)
        self.assertEqual(client.calls[0][2], 'domain_analyzer:analysis_concurrency')
        self.assertEqual(client.calls[0][3], 180000)
        self.assertEqual(client.calls[0][4], 2)
        self.assertEqual(client.calls[0][5], 'task-1')

    async def test_reports_busy_slot_without_fallback(self) -> None:
        limiter = RedisAnalysisConcurrencyLimiter(max_concurrency=1, lease_seconds=180)
        limiter._client = FakeRedis([0])

        self.assertFalse(await limiter.acquire('task-2'))

    async def test_reports_redis_failure(self) -> None:
        limiter = RedisAnalysisConcurrencyLimiter()
        limiter._client = FailingRedis()

        with self.assertRaises(AnalysisConcurrencyUnavailableError):
            await limiter.acquire('task-1')

    async def test_releases_slot_after_operation(self) -> None:
        limiter = RedisAnalysisConcurrencyLimiter()
        limiter.acquire = AsyncMock(return_value=True)
        limiter.release = AsyncMock()
        operation = AsyncMock(return_value='result')

        result = await run_with_concurrency_limit('task-1', operation, limiter=limiter)

        self.assertEqual(result, 'result')
        operation.assert_awaited_once_with()
        limiter.acquire.assert_awaited_once_with('task-1')
        limiter.release.assert_awaited_once_with('task-1')


if __name__ == '__main__':
    unittest.main()
