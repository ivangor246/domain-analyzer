import unittest

from app.core.exceptions import RateLimitUnavailableError
from app.core.rate_limit import RateLimiter, RedisRateLimiter


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_sliding_window_expires_old_requests(self):
        current_time = [0.0]
        limiter = RateLimiter(2, 10, clock=lambda: current_time[0])

        first = await limiter.check('client')
        second = await limiter.check('client')
        blocked = await limiter.check('client')

        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.allowed)
        self.assertEqual(second.remaining, 0)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.retry_after, 10)

        current_time[0] = 10.0
        after_window = await limiter.check('client')
        self.assertTrue(after_window.allowed)
        self.assertEqual(after_window.remaining, 1)


class FakeRedis:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def eval(self, *args):
        self.calls.append(args)
        return self.response


class FailingRedis:
    def eval(self, *_args):
        raise ConnectionError('Redis unavailable')


class RedisRateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_atomic_redis_script_response(self) -> None:
        client = FakeRedis([1, 4, 0])
        limiter = RedisRateLimiter(5, 60)
        limiter._client = client

        result = await limiter.check('client')

        self.assertTrue(result.allowed)
        self.assertEqual(result.remaining, 4)
        self.assertIsNone(result.retry_after)
        self.assertEqual(client.calls[0][1], 1)
        self.assertTrue(client.calls[0][2].startswith('domain_analyzer:rate_limit:'))

    async def test_maps_blocked_redis_response(self) -> None:
        limiter = RedisRateLimiter(5, 60)
        limiter._client = FakeRedis([0, 0, 12])

        result = await limiter.check('client')

        self.assertFalse(result.allowed)
        self.assertEqual(result.remaining, 0)
        self.assertEqual(result.retry_after, 12)

    async def test_falls_back_when_redis_is_unavailable(self) -> None:
        limiter = RedisRateLimiter(1, 60, fallback=RateLimiter(1, 60))
        limiter._client = FailingRedis()

        first = await limiter.check('client')
        second = await limiter.check('client')

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)

    async def test_can_fail_closed_when_fallback_is_disabled(self) -> None:
        limiter = RedisRateLimiter(1, 60)
        limiter._client = FailingRedis()

        with self.assertRaises(RateLimitUnavailableError):
            await limiter.check('client')


if __name__ == '__main__':
    unittest.main()
