import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.core.config import settings
from app.services import geoip, rdap_client
from app.services.rdap_bootstrap import RDAPBootstrap
from app.services.rdap_client import RDAPClient
from app.utils.ttl_cache import AsyncTTLCache


class ProviderCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await geoip.geoip_cache.clear()
        await rdap_client.rdap_cache.clear()
        await rdap_client.rdap_breaker.reset()

        self._bootstrap_state = (
            RDAPBootstrap._instance,
            RDAPBootstrap._loaded_at,
            RDAPBootstrap._loaded_source,
            RDAPBootstrap._load_lock,
        )
        self.addAsyncCleanup(geoip.geoip_cache.clear)
        self.addAsyncCleanup(rdap_client.rdap_cache.clear)
        self.addAsyncCleanup(rdap_client.rdap_breaker.reset)
        self.addCleanup(self._restore_bootstrap_state)

    def _restore_bootstrap_state(self) -> None:
        (
            RDAPBootstrap._instance,
            RDAPBootstrap._loaded_at,
            RDAPBootstrap._loaded_source,
            RDAPBootstrap._load_lock,
        ) = self._bootstrap_state

    async def test_ttl_cache_expires_entries_and_bounds_memory(self) -> None:
        cache = AsyncTTLCache[str, str](max_entries=1)

        await cache.set('first', 'value', ttl_seconds=60)
        await cache.set('second', 'value', ttl_seconds=60)
        self.assertIsNone(await cache.get('first'))
        self.assertEqual(await cache.get('second'), 'value')

        await cache.set('temporary', 'value', ttl_seconds=0.01)
        await asyncio.sleep(0.02)
        self.assertIsNone(await cache.get('temporary'))

    async def test_geoip_cache_avoids_repeating_successful_provider_call(self) -> None:
        ip = '203.0.113.10'
        response_payload = [
            {
                'status': 'success',
                'query': ip,
                'country': 'Exampleland',
                'countryCode': 'EX',
            }
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response_payload, request=request)

        first_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(geoip.httpx, 'AsyncClient', return_value=first_client) as client_mock:
            first = await geoip.GeoIPService.lookup([ip])
        client_mock.assert_called_once()

        with patch.object(geoip.httpx, 'AsyncClient') as client_mock:
            second = await geoip.GeoIPService.lookup([ip])

        client_mock.assert_not_called()
        self.assertEqual(first, second)
        self.assertEqual(second[ip].country, 'Exampleland')

    async def test_rdap_cache_avoids_repeating_successful_provider_call(self) -> None:
        server = 'https://rdap.example.test'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={'status': ['active']}, request=request)

        first_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(rdap_client.httpx, 'AsyncClient', return_value=first_client) as client_mock,
            patch.object(
                rdap_client.NetworkTargetGuard,
                'resolve_public_ips',
                new=AsyncMock(return_value=['203.0.113.11']),
            ),
        ):
            first = await RDAPClient.query('Example.COM', [server])
        client_mock.assert_called_once()

        with patch.object(rdap_client.httpx, 'AsyncClient') as client_mock:
            second = await RDAPClient.query('example.com', [server])

        client_mock.assert_not_called()
        self.assertEqual(first, second)
        self.assertEqual(second.status, ['active'])

    async def test_rdap_bootstrap_refreshes_after_ttl(self) -> None:
        old_instance = RDAPBootstrap()
        RDAPBootstrap._instance = old_instance
        RDAPBootstrap._loaded_at = time.monotonic() - settings.RDAP_BOOTSTRAP_CACHE_TTL_SECONDS - 1
        RDAPBootstrap._loaded_source = settings.BOOTSTRAP_URL
        RDAPBootstrap._load_lock = None

        with patch.object(RDAPBootstrap, 'load', new=AsyncMock()) as load:
            refreshed = await RDAPBootstrap.get_instance()

        self.assertIsNot(refreshed, old_instance)
        load.assert_awaited_once()
        self.assertEqual(RDAPBootstrap._loaded_source, settings.BOOTSTRAP_URL)


if __name__ == '__main__':
    unittest.main()
