import unittest
from unittest.mock import AsyncMock, patch

from app.services import health


class HealthChecksTestCase(unittest.IsolatedAsyncioTestCase):
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
