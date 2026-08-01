import asyncio
import unittest
from unittest.mock import AsyncMock

from app.utils.circuit_breaker import CircuitOpenError, CircuitBreaker


class CircuitBreakerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_opens_after_transient_failures_and_skips_calls(self) -> None:
        breaker = CircuitBreaker(failure_threshold=2, reset_seconds=30)
        operation = AsyncMock(side_effect=ConnectionError('provider unavailable'))

        with self.assertRaises(ConnectionError):
            await breaker.call('provider', operation)
        with self.assertRaises(ConnectionError):
            await breaker.call('provider', operation)
        with self.assertRaises(CircuitOpenError):
            await breaker.call('provider', operation)

        self.assertEqual(operation.await_count, 2)
        self.assertTrue(await breaker.is_open('provider'))

    async def test_half_open_probe_closes_the_circuit_after_reset_window(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, reset_seconds=0)
        failed = AsyncMock(side_effect=ConnectionError('provider unavailable'))
        recovered = AsyncMock(return_value='ok')

        with self.assertRaises(ConnectionError):
            await breaker.call('provider', failed)

        self.assertEqual(await breaker.call('provider', recovered), 'ok')
        self.assertFalse(await breaker.is_open('provider'))

    async def test_cancelled_half_open_probe_releases_probe_slot(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, reset_seconds=0)
        failed = AsyncMock(side_effect=ConnectionError('provider unavailable'))

        with self.assertRaises(ConnectionError):
            await breaker.call('provider', failed)

        started = asyncio.Event()

        async def blocked_operation() -> None:
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(breaker.call('provider', blocked_operation))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(await breaker.call('provider', AsyncMock(return_value='ok')), 'ok')

    async def test_non_transient_errors_do_not_open_the_circuit(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, reset_seconds=30)
        operation = AsyncMock(side_effect=ValueError('invalid provider payload'))

        with self.assertRaises(ValueError):
            await breaker.call('provider', operation, should_trip=lambda exc: isinstance(exc, ConnectionError))

        self.assertFalse(await breaker.is_open('provider'))


if __name__ == '__main__':
    unittest.main()
