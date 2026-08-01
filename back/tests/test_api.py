import re
import unittest

import httpx

from app.main import create_app


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transport = httpx.ASGITransport(app=create_app())
        self.client = httpx.AsyncClient(transport=self.transport, base_url='http://test')

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_check_returns_status_and_request_id(self) -> None:
        response = await self.client.get('/api/health')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertRegex(response.headers['X-Request-ID'], re.compile(r'^[0-9a-f]{32}$'))

    async def test_invalid_domain_returns_consistent_error(self) -> None:
        response = await self.client.get('/api/domain', params={'d': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'code': 'invalid_domain', 'message': 'Invalid domain format'},
        )

    async def test_missing_domain_returns_validation_error(self) -> None:
        response = await self.client.get('/api/domain')

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'request_validation_error')
        self.assertNotIn('detail', response.json())

    async def test_unknown_route_returns_consistent_error(self) -> None:
        response = await self.client.get('/missing')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'code': 'http_error', 'message': 'Not Found'})
