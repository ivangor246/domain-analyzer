import re
import unittest

import httpx
from unittest.mock import patch

from app.api import analyses
from app.core.config import settings
from app.main import create_app
from app.schemas.analysis import AnalysisJobSchema, AnalysisStatus


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

    async def test_domain_endpoint_returns_rate_limit_error(self) -> None:
        with patch.object(settings, 'RATE_LIMIT_REQUESTS', 1):
            app = create_app()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url='http://test',
        ) as client:
            first_response = await client.get('/api/domain', params={'d': 'invalid'})
            second_response = await client.get('/api/domain', params={'d': 'invalid'})

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(
            second_response.json(),
            {'code': 'rate_limit_exceeded', 'message': 'Too many requests. Try again later.'},
        )
        self.assertEqual(second_response.headers['X-RateLimit-Limit'], '1')
        self.assertEqual(second_response.headers['X-RateLimit-Remaining'], '0')
        self.assertEqual(second_response.headers['Retry-After'], '60')

    def test_openapi_describes_domain_contract(self) -> None:
        schema = create_app().openapi()
        operation = schema['paths']['/api/domain']['get']

        self.assertEqual(operation['summary'], 'Analyze a domain')
        self.assertEqual(
            operation['responses']['200']['description'], 'Structured domain analysis with optional partial results.'
        )
        self.assertIn('400', operation['responses'])
        self.assertIn('422', operation['responses'])
        self.assertIn('429', operation['responses'])
        self.assertEqual(operation['parameters'][0]['name'], 'd')
        self.assertEqual(operation['parameters'][0]['schema']['maxLength'], settings.MAX_DOMAIN_LENGTH)

    async def test_analysis_job_endpoints_use_async_contract(self) -> None:
        job = AnalysisJobSchema(
            id='a' * 32,
            domain='example.com',
            status=AnalysisStatus.QUEUED,
            created_at='2026-01-01T00:00:00Z',
        )

        class FakeAnalysisService:
            async def create(self, domain: str, idempotency_key: str | None = None) -> AnalysisJobSchema:
                self.created = (domain, idempotency_key)
                return job

            async def get(self, analysis_id: str) -> AnalysisJobSchema:
                self.requested = analysis_id
                return job

            async def cancel(self, analysis_id: str) -> AnalysisJobSchema:
                self.cancelled = analysis_id
                return job.model_copy(update={'status': AnalysisStatus.CANCELLED})

        fake_service = FakeAnalysisService()
        with patch.object(analyses, 'service', fake_service):
            created = await self.client.post(
                '/api/analyses',
                json={'domain': 'example.com'},
                headers={'Idempotency-Key': 'request-1'},
            )
            received = await self.client.get(f'/api/analyses/{job.id}')
            cancelled = await self.client.post(f'/api/analyses/{job.id}/cancel')

        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()['status'], 'queued')
        self.assertEqual(fake_service.created, ('example.com', 'request-1'))
        self.assertEqual(received.status_code, 200)
        self.assertEqual(fake_service.requested, job.id)
        self.assertEqual(cancelled.json()['status'], 'cancelled')
        self.assertEqual(fake_service.cancelled, job.id)

    async def test_invalid_async_analysis_domain_returns_consistent_error(self) -> None:
        response = await self.client.post('/api/analyses', json={'domain': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'code': 'invalid_domain', 'message': 'Invalid domain format'})

    def test_openapi_describes_async_analysis_contract(self) -> None:
        schema = create_app().openapi()

        self.assertIn('/api/analyses', schema['paths'])
        self.assertIn('/api/analyses/{analysis_id}', schema['paths'])
        self.assertIn('/api/analyses/{analysis_id}/cancel', schema['paths'])
        self.assertEqual(
            schema['paths']['/api/analyses']['post']['responses']['202']['description'],
            'Successful Response',
        )

    async def test_cors_allows_configured_frontend_origin(self) -> None:
        response = await self.client.options(
            '/api/analyses',
            headers={
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type,idempotency-key',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:5173')
        self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])
        self.assertIn('Idempotency-Key', response.headers['Access-Control-Allow-Headers'])
