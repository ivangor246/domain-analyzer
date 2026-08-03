import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services import health


class HealthChecksTestCase(unittest.IsolatedAsyncioTestCase):
    def test_worker_ping_leaves_time_for_outer_timeout(self) -> None:
        inspector = Mock()
        inspector.ping.return_value = {'worker': {'ok': 'pong'}}
        control = Mock()
        control.inspect.return_value = inspector

        with (
            patch.object(health.settings, 'REDIS_TIMEOUT_SECONDS', 5.0),
            patch('app.core.celery_app.celery_app.control', control),
        ):
            result = health._ping_worker_sync()

        self.assertTrue(result)
        control.inspect.assert_called_once_with(timeout=4.0)

    async def test_check_dependencies_maps_successful_checks(self) -> None:
        with (
            patch.object(health, 'check_redis', new=AsyncMock(return_value=True)),
            patch.object(health, 'check_worker', new=AsyncMock(return_value=False)),
        ):
            result = await health.check_dependencies()

        self.assertEqual(result, {'redis': True, 'worker': False})

    async def test_check_dependencies_treats_unexpected_check_errors_as_unavailable(self) -> None:
        with (
            patch.object(health, 'check_redis', new=AsyncMock(side_effect=RuntimeError('Redis unavailable'))),
            patch.object(health, 'check_worker', new=AsyncMock(return_value=True)),
        ):
            result = await health.check_dependencies()

        self.assertEqual(result, {'redis': False, 'worker': True})


if __name__ == '__main__':
    unittest.main()
