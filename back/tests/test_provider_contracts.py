import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services import geoip, rdap_bootstrap, rdap_client
from app.services.geoip import GeoIPService
from app.services.rdap_client import RDAPClient
from app.services.rdap_bootstrap import RDAPBootstrap


class ProviderContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await geoip.geoip_cache.clear()
        await geoip.geoip_breaker.reset()
        await rdap_client.rdap_cache.clear()
        await rdap_client.rdap_breaker.reset()
        await RDAPBootstrap._breaker.reset()
        self.addAsyncCleanup(geoip.geoip_cache.clear)
        self.addAsyncCleanup(geoip.geoip_breaker.reset)
        self.addAsyncCleanup(rdap_client.rdap_cache.clear)
        self.addAsyncCleanup(rdap_client.rdap_breaker.reset)
        self.addAsyncCleanup(RDAPBootstrap._breaker.reset)

    async def test_rdap_retries_transient_upstream_response(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(503, request=request)
            return httpx.Response(200, json={'status': ['active']}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(rdap_client.NetworkTargetGuard, 'validate', new=AsyncMock()),
            patch.object(rdap_client.settings, 'RDAP_MAX_RETRIES', 1),
            patch.object(rdap_client.settings, 'RETRY_BACKOFF_SECONDS', 0),
            patch.object(rdap_client.settings, 'RETRY_JITTER_SECONDS', 0),
        ):
            result = await RDAPClient._query_server(client, 'example.com', 'https://rdap.example.test')
        await client.aclose()

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ['active'])
        self.assertEqual(len(requests), 2)

    async def test_rdap_ignores_malformed_json_without_retrying(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b'not-json', request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(rdap_client.NetworkTargetGuard, 'validate', new=AsyncMock()),
            patch.object(rdap_client.settings, 'RDAP_MAX_RETRIES', 1),
        ):
            result = await RDAPClient._query_server(client, 'example.com', 'https://rdap.example.test')
        await client.aclose()

        self.assertIsNone(result)
        self.assertEqual(len(requests), 1)

    async def test_geoip_retries_transient_upstream_response(self) -> None:
        requests: list[httpx.Request] = []
        ip = '8.8.8.8'

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(429, request=request)
            return httpx.Response(
                200,
                json=[{'status': 'success', 'query': ip, 'country': 'Exampleland'}],
                request=request,
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(geoip.httpx, 'AsyncClient', return_value=client),
            patch.object(geoip.settings, 'GEOIP_MAX_RETRIES', 1),
            patch.object(geoip.settings, 'RETRY_BACKOFF_SECONDS', 0),
            patch.object(geoip.settings, 'RETRY_JITTER_SECONDS', 0),
        ):
            data = await GeoIPService._fetch([ip])

        self.assertEqual(len(requests), 2)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]['query'], ip)

    async def test_geoip_returns_no_records_for_malformed_payload(self) -> None:
        ip = '8.8.8.8'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={'status': 'success', 'query': ip}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(geoip.httpx, 'AsyncClient', return_value=client):
            result = await GeoIPService.lookup([ip])

        self.assertEqual(result, {})

    async def test_rdap_bootstrap_rejects_payload_without_valid_services(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={'services': [None, ['not-a-list', []], [[], ['   ']]]},
                request=request,
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(rdap_bootstrap.httpx, 'AsyncClient', return_value=client):
            with self.assertRaises(ValueError):
                await RDAPBootstrap().load()


if __name__ == '__main__':
    unittest.main()
