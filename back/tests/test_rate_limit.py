import unittest

from app.core.rate_limit import RateLimiter


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


if __name__ == '__main__':
    unittest.main()
