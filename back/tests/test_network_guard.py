import unittest
from unittest.mock import patch

from app.core.exceptions import TargetNotAllowedError
from app.services.network_guard import NetworkTargetGuard


class FakeLoop:
    def __init__(self, address: str):
        self.address = address

    async def getaddrinfo(self, host, port, type):
        return [(2, 1, 6, '', (self.address, 0))]


class NetworkTargetGuardTestCase(unittest.IsolatedAsyncioTestCase):
    def test_public_ip_detection(self) -> None:
        self.assertTrue(NetworkTargetGuard.is_public_ip('8.8.8.8'))
        self.assertTrue(NetworkTargetGuard.is_public_ip('2001:4860:4860::8888'))
        self.assertFalse(NetworkTargetGuard.is_public_ip('127.0.0.1'))
        self.assertFalse(NetworkTargetGuard.is_public_ip('10.0.0.1'))
        self.assertFalse(NetworkTargetGuard.is_public_ip('192.0.2.1'))
        self.assertFalse(NetworkTargetGuard.is_public_ip('::1'))

    async def test_rejects_non_public_resolution(self) -> None:
        loop = FakeLoop('127.0.0.1')
        with patch('app.services.network_guard.asyncio.get_running_loop', return_value=loop):
            with self.assertRaises(TargetNotAllowedError):
                await NetworkTargetGuard.validate('internal.test')

    async def test_accepts_public_resolution(self) -> None:
        loop = FakeLoop('8.8.8.8')
        with patch('app.services.network_guard.asyncio.get_running_loop', return_value=loop):
            await NetworkTargetGuard.validate('public.test')

    async def test_returns_public_resolution_for_fixed_target_connections(self) -> None:
        loop = FakeLoop('8.8.8.8')
        with patch('app.services.network_guard.asyncio.get_running_loop', return_value=loop):
            addresses = await NetworkTargetGuard.resolve_public_ips('public.test')

        self.assertEqual(addresses, ['8.8.8.8'])
