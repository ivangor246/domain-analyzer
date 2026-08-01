import asyncio
import unittest
from unittest.mock import patch

from app.core.config import settings
from app.core.exceptions import AnalysisTimeoutError
from app.schemas.analysis import ANALYSIS_CHECKS
from app.schemas.dns import PropagationSchema
from app.schemas.http import HTTPSchema
from app.schemas.latency import LatencySchema
from app.schemas.ports import PortsSchema
from app.schemas.ssl import SSLSchema
from app.services.dns_resolver import DNSRecords
from app.services.domain import DomainDependencies, DomainService


class FakeGuard:
    @staticmethod
    async def resolve_public_ips(host: str) -> list[str]:
        return ['8.8.8.8']


class SlowGuard:
    @staticmethod
    async def resolve_public_ips(host: str) -> list[str]:
        await asyncio.sleep(1)
        return ['8.8.8.8']


class FakeBootstrap:
    @classmethod
    async def get_instance(cls):
        return cls()

    def get_servers(self, domain: str) -> tuple[list[str], str]:
        return ['https://rdap.test'], domain


class SlowBootstrap:
    @classmethod
    async def get_instance(cls):
        await asyncio.sleep(1)
        return cls()


class FakeRDAP:
    @staticmethod
    async def query(domain: str, servers: list[str]):
        raise RuntimeError('RDAP unavailable')


class FakeDNS:
    @staticmethod
    async def resolve(domain: str) -> DNSRecords:
        return DNSRecords(A=['8.8.8.8'])


class SlowDNS:
    @staticmethod
    async def resolve(domain: str) -> DNSRecords:
        await asyncio.sleep(1)
        return DNSRecords(A=['8.8.8.8'])


class FakePropagation:
    @staticmethod
    async def check(domain: str) -> PropagationSchema:
        return PropagationSchema(consistent=True)


class FakeHTTP:
    @staticmethod
    async def probe(domain: str, target_ips: list[str]) -> HTTPSchema:
        return HTTPSchema()


class FakeSSL:
    @staticmethod
    async def check(domain: str, target_ips: list[str]) -> SSLSchema:
        return SSLSchema(valid=True)


class FakePorts:
    @staticmethod
    async def scan(host: str, target_ips: list[str]) -> PortsSchema:
        return PortsSchema()


class FakeLatency:
    @staticmethod
    async def measure(host: str, target_ips: list[str]) -> LatencySchema:
        return LatencySchema()


class FakeGeoIP:
    @staticmethod
    async def lookup(ips: list[str]):
        return {}


class DomainServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_failed_check_does_not_hide_successful_results(self) -> None:
        dependencies = DomainDependencies(
            rdap_bootstrap=FakeBootstrap,
            rdap_client=FakeRDAP,
            dns_resolver=FakeDNS,
            dns_propagation=FakePropagation,
            geoip_service=FakeGeoIP,
            http_service=FakeHTTP,
            ssl_service=FakeSSL,
            port_scanner=FakePorts,
            latency_service=FakeLatency,
            network_guard=FakeGuard,
        )

        progress: list[tuple[str, str, float | None]] = []

        async def on_progress(check: str, status: str, duration_ms: float | None = None) -> None:
            progress.append((check, status, duration_ms))

        result = await DomainService(dependencies).analyze('example.com', progress_callback=on_progress)

        self.assertEqual(result.dns.A, ['8.8.8.8'])
        self.assertIsNone(result.rdap_server)
        self.assertEqual({error.check for error in result.analysis_errors}, {'rdap'})
        latest_status = {check: status for check, status, _duration_ms in progress}
        self.assertEqual(latest_status['rdap'], 'failed')
        self.assertEqual(latest_status['dns'], 'successful')
        self.assertEqual(latest_status['geoip'], 'successful')
        self.assertIsNotNone(result.metadata)
        self.assertGreaterEqual(result.metadata.duration_ms, 0)
        self.assertEqual(result.metadata.checks['rdap'].status, 'failed')
        self.assertIn('https://data.iana.org', result.metadata.checks['rdap'].sources)
        self.assertGreaterEqual(result.metadata.checks['dns'].duration_ms, 0)

    async def test_global_deadline_preserves_partial_results(self) -> None:
        dependencies = DomainDependencies(
            rdap_bootstrap=FakeBootstrap,
            rdap_client=FakeRDAP,
            dns_resolver=SlowDNS,
            dns_propagation=FakePropagation,
            geoip_service=FakeGeoIP,
            http_service=FakeHTTP,
            ssl_service=FakeSSL,
            port_scanner=FakePorts,
            latency_service=FakeLatency,
            network_guard=FakeGuard,
        )

        with patch.object(settings, 'ANALYSIS_TIMEOUT_SECONDS', 0.01):
            result = await DomainService(dependencies).analyze('example.com')

        self.assertEqual(result.dns.A, [])
        self.assertIn('dns_timeout', {error.code for error in result.analysis_errors})

    async def test_global_deadline_marks_unstarted_checks_as_timed_out(self) -> None:
        dependencies = DomainDependencies(
            rdap_bootstrap=SlowBootstrap,
            rdap_client=FakeRDAP,
            dns_resolver=FakeDNS,
            dns_propagation=FakePropagation,
            geoip_service=FakeGeoIP,
            http_service=FakeHTTP,
            ssl_service=FakeSSL,
            port_scanner=FakePorts,
            latency_service=FakeLatency,
            network_guard=FakeGuard,
        )
        progress: list[tuple[str, str, float | None]] = []

        async def on_progress(check: str, status: str, duration_ms: float | None = None) -> None:
            progress.append((check, status, duration_ms))

        with patch.object(settings, 'ANALYSIS_TIMEOUT_SECONDS', 0.01):
            result = await DomainService(dependencies).analyze('example.com', progress_callback=on_progress)

        self.assertEqual({error.check for error in result.analysis_errors}, set(ANALYSIS_CHECKS))
        self.assertIsNotNone(result.metadata)
        self.assertEqual(set(result.metadata.checks), set(ANALYSIS_CHECKS))
        self.assertTrue(all(item.status == 'timeout' for item in result.metadata.checks.values()))
        latest_progress = {check: (status, duration_ms) for check, status, duration_ms in progress}
        self.assertEqual(set(latest_progress), set(ANALYSIS_CHECKS))
        self.assertTrue(all(status == 'failed' for status, _duration_ms in latest_progress.values()))
        self.assertTrue(all(duration_ms is not None for _status, duration_ms in latest_progress.values()))

    async def test_global_deadline_rejects_target_validation_timeout(self) -> None:
        dependencies = DomainDependencies(network_guard=SlowGuard)

        with patch.object(settings, 'ANALYSIS_TIMEOUT_SECONDS', 0.01):
            with self.assertRaises(AnalysisTimeoutError):
                await DomainService(dependencies).analyze('example.com')
