import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, TypeVar
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.exceptions import AnalysisTimeoutError, DomainValidationError
from app.core.metrics import record_analysis, record_analysis_check
from app.schemas.analysis import ANALYSIS_CHECKS
from app.schemas.dns import DNSSchema, PropagationSchema
from app.schemas.domain import AnalysisCheckMetadata, AnalysisError, AnalysisMetadata, DomainSchema
from app.schemas.geoip import GeoIPRecord
from app.schemas.http import HTTPSchema
from app.schemas.latency import LatencySchema
from app.schemas.ports import PortsSchema
from app.schemas.ssl import SSLSchema
from app.utils.domain_validator import validate_domain

from .dns_propagation import DNSPropagation
from .dns_resolver import DNSResolver, DNSRecords
from .geoip import GeoIPService
from .http_headers import HTTPHeadersService
from .latency import LatencyService
from .network_guard import NetworkTargetGuard
from .port_scanner import PortScanner
from .rdap_bootstrap import RDAPBootstrap
from .rdap_client import RDAPClient, RDAPResponse
from .ssl_cert import SSLCertService

logger = logging.getLogger(__name__)

T = TypeVar('T')
ProgressCallback = Callable[[str, str, float | None], Awaitable[None]]
CheckObservationStatus = Literal['successful', 'failed', 'timeout', 'cancelled']


@dataclass(frozen=True)
class _CheckObservation:
    status: CheckObservationStatus
    completed_at: datetime
    duration_ms: float


_ANALYSIS_FAILURES: dict[str, tuple[str, str]] = {
    'rdap': ('rdap_unavailable', 'RDAP analysis failed.'),
    'dns': ('dns_unavailable', 'DNS analysis failed.'),
    'dns_propagation': ('dns_propagation_unavailable', 'DNS propagation analysis failed.'),
    'geoip': ('geoip_unavailable', 'GeoIP analysis failed.'),
    'http': ('http_unavailable', 'HTTP analysis failed.'),
    'ssl': ('ssl_unavailable', 'TLS analysis failed.'),
    'ports': ('ports_unavailable', 'Port scan failed.'),
    'latency': ('latency_unavailable', 'Latency analysis failed.'),
}


@dataclass(frozen=True)
class DomainDependencies:
    rdap_bootstrap: type[RDAPBootstrap] = RDAPBootstrap
    rdap_client: type[RDAPClient] = RDAPClient
    dns_resolver: type[DNSResolver] = DNSResolver
    dns_propagation: type[DNSPropagation] = DNSPropagation
    geoip_service: type[GeoIPService] = GeoIPService
    http_service: type[HTTPHeadersService] = HTTPHeadersService
    ssl_service: type[SSLCertService] = SSLCertService
    port_scanner: type[PortScanner] = PortScanner
    latency_service: type[LatencyService] = LatencyService
    network_guard: type[NetworkTargetGuard] = NetworkTargetGuard


def _analysis_error(check: str, timed_out: bool = False) -> AnalysisError:
    if timed_out:
        return AnalysisError(
            check=check,
            code=f'{check}_timeout',
            message='Analysis check exceeded the global deadline.',
        )

    code, message = _ANALYSIS_FAILURES[check]
    logger.warning('domain analysis check failed', extra={'check': check})
    return AnalysisError(check=check, code=code, message=message)


def _record_observation(
    observations: dict[str, _CheckObservation],
    check: str,
    started_at: float,
    status: CheckObservationStatus,
) -> None:
    observations[check] = _CheckObservation(
        status=status,
        completed_at=datetime.now(timezone.utc),
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


def _safe_source_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        if not parsed.scheme or not parsed.hostname:
            return 'configured provider'
        hostname = parsed.hostname
        if ':' in hostname:
            hostname = f'[{hostname}]'
        port = f':{parsed.port}' if parsed.port is not None else ''
    except ValueError:
        return 'configured provider'
    return f'{parsed.scheme}://{hostname}{port}'


def _sources_for_check(check: str, domain: str, rdap_result: RDAPResponse | None) -> list[str]:
    if check == 'rdap':
        sources = [_safe_source_url(settings.BOOTSTRAP_URL)]
        if rdap_result is not None:
            sources.append(_safe_source_url(rdap_result.server))
        return list(dict.fromkeys(sources))
    if check == 'dns':
        return [f'dns://{server}' for server in settings.DNS_SERVERS]
    if check == 'dns_propagation':
        return [f'{server["name"]} ({server["ip"]})' for server in settings.PROPAGATION_SERVERS]
    if check == 'geoip':
        return [_safe_source_url(settings.GEOIP_URL)]
    if check == 'http':
        return [f'http://{domain}', f'https://{domain}']
    if check == 'ssl':
        return [f'tls://{domain}:443']
    if check == 'ports':
        return [f'tcp://{domain}']
    if check == 'latency':
        return [f'tcp://{domain}:80', f'tcp://{domain}:443']
    return []


def _build_analysis_metadata(
    started_at: datetime,
    completed_at: datetime,
    duration_ms: float,
    domain: str,
    observations: dict[str, _CheckObservation],
    rdap_result: RDAPResponse | None,
) -> AnalysisMetadata:
    return AnalysisMetadata(
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        checks={
            check: AnalysisCheckMetadata(
                status=observation.status,
                completed_at=observation.completed_at,
                duration_ms=observation.duration_ms,
                sources=_sources_for_check(check, domain, rdap_result),
            )
            for check, observation in observations.items()
        },
    )


async def _report_progress(
    progress_callback: ProgressCallback | None,
    check: str,
    status: str,
    duration_ms: float | None = None,
) -> None:
    if progress_callback is None:
        return

    try:
        await progress_callback(check, status, duration_ms)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning(
            'domain analysis progress update failed',
            extra={'check': check, 'check_status': status},
        )


def _result_or_default(
    results: dict[str, object],
    check: str,
    expected_type: type[T],
    default: T | None,
    errors: list[AnalysisError],
) -> T | None:
    result = results.get(check)
    if isinstance(result, asyncio.CancelledError):
        raise result
    if isinstance(result, asyncio.TimeoutError):
        errors.append(_analysis_error(check, timed_out=True))
        return default
    if not isinstance(result, expected_type):
        errors.append(_analysis_error(check))
        return default
    return result


async def _load_rdap_context(
    domain: str,
    errors: list[AnalysisError],
    dependencies: DomainDependencies,
    deadline: float,
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
) -> tuple[list[str], str]:
    started_at = perf_counter()
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        errors.append(_analysis_error('rdap', timed_out=True))
        await _record_rdap_context_failure(
            domain,
            analysis_id=analysis_id,
            task_id=task_id,
            progress_callback=progress_callback,
            observations=observations,
            started_at=started_at,
            timed_out=True,
        )
        return [], domain

    try:
        bootstrap = await asyncio.wait_for(dependencies.rdap_bootstrap.get_instance(), timeout=remaining)
        servers, rdap_domain = bootstrap.get_servers(domain=domain)
        if servers:
            return servers, rdap_domain
    except asyncio.TimeoutError:
        errors.append(_analysis_error('rdap', timed_out=True))
        await _record_rdap_context_failure(
            domain,
            analysis_id=analysis_id,
            task_id=task_id,
            progress_callback=progress_callback,
            observations=observations,
            started_at=started_at,
            timed_out=True,
        )
        return [], domain
    except asyncio.CancelledError:
        raise
    except Exception:
        pass

    errors.append(_analysis_error('rdap'))
    await _record_rdap_context_failure(
        domain,
        analysis_id=analysis_id,
        task_id=task_id,
        progress_callback=progress_callback,
        observations=observations,
        started_at=started_at,
        timed_out=False,
    )
    return [], domain


async def _record_rdap_context_failure(
    domain: str,
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
    started_at: float,
    timed_out: bool,
) -> None:
    status: CheckObservationStatus = 'timeout' if timed_out else 'failed'
    metric_status = 'timeout' if timed_out else 'failed'
    _record_observation(observations, 'rdap', started_at, status)
    duration_seconds = perf_counter() - started_at
    duration_ms = round(duration_seconds * 1000, 2)
    record_analysis_check('rdap', metric_status, duration_seconds)
    logger.info(
        'domain analysis check completed',
        extra={
            'domain': domain,
            'check': 'rdap',
            'analysis_id': analysis_id,
            'task_id': task_id,
            'check_status': metric_status,
            'check_duration_ms': duration_ms,
        },
    )
    await _report_progress(progress_callback, 'rdap', 'failed', duration_ms)


async def _run_check(
    check: str,
    domain: str,
    operation: Callable[[], Awaitable[Any]],
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
    deadline_expired: asyncio.Event,
) -> Any:
    started_at = perf_counter()
    progress_status = 'successful'
    metric_status = 'success'
    observation_status: CheckObservationStatus = 'successful'
    await _report_progress(progress_callback, check, 'running')
    try:
        return await operation()
    except asyncio.TimeoutError:
        progress_status = 'failed'
        metric_status = 'timeout'
        observation_status = 'timeout'
        raise
    except asyncio.CancelledError:
        progress_status = 'failed'
        if deadline_expired.is_set():
            metric_status = 'timeout'
            observation_status = 'timeout'
        else:
            metric_status = 'cancelled'
            observation_status = 'cancelled'
        raise
    except Exception:
        progress_status = 'failed'
        metric_status = 'failed'
        observation_status = 'failed'
        raise
    finally:
        duration_seconds = perf_counter() - started_at
        _record_observation(observations, check, started_at, observation_status)
        record_analysis_check(check, metric_status, duration_seconds)
        logger.info(
            'domain analysis check completed',
            extra={
                'domain': domain,
                'check': check,
                'analysis_id': analysis_id,
                'task_id': task_id,
                'check_status': metric_status,
                'check_duration_ms': round(duration_seconds * 1000, 2),
            },
        )
        await _report_progress(progress_callback, check, progress_status, round(duration_seconds * 1000, 2))


async def _record_unstarted_timeout(
    check: str,
    domain: str,
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
) -> None:
    started_at = perf_counter()
    _record_observation(observations, check, started_at, 'timeout')
    duration_seconds = perf_counter() - started_at
    duration_ms = round(duration_seconds * 1000, 2)
    record_analysis_check(check, 'timeout', duration_seconds)
    logger.info(
        'domain analysis check completed',
        extra={
            'domain': domain,
            'check': check,
            'analysis_id': analysis_id,
            'task_id': task_id,
            'check_status': 'timeout',
            'check_duration_ms': duration_ms,
        },
    )
    await _report_progress(progress_callback, check, 'failed', duration_ms)


async def _wait_for_tasks(
    tasks: dict[str, asyncio.Task[Any]],
    deadline: float,
    deadline_expired: asyncio.Event,
) -> set[asyncio.Task[Any]]:
    done: set[asyncio.Task[Any]] = set()
    pending: set[asyncio.Task[Any]] = set()
    try:
        remaining = max(0, deadline - asyncio.get_running_loop().time())
        done, pending = await asyncio.wait(tasks.values(), timeout=remaining)
        if pending:
            deadline_expired.set()
        return done
    except asyncio.CancelledError:
        pending = set(tasks.values())
        raise
    finally:
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


async def _collect_results(
    domain: str,
    target_ips: list[str],
    servers: list[str],
    rdap_domain: str,
    dependencies: DomainDependencies,
    deadline: float,
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
) -> dict[str, object]:
    operations: dict[str, Callable[[], Awaitable[Any]]] = {
        'dns': lambda: dependencies.dns_resolver.resolve(domain=domain),
        'dns_propagation': lambda: dependencies.dns_propagation.check(domain=domain),
        'http': lambda: dependencies.http_service.probe(domain=domain, target_ips=target_ips),
        'ssl': lambda: dependencies.ssl_service.check(domain=domain, target_ips=target_ips),
        'ports': lambda: dependencies.port_scanner.scan(host=domain, target_ips=target_ips),
        'latency': lambda: dependencies.latency_service.measure(host=domain, target_ips=target_ips),
    }
    if servers:
        operations['rdap'] = lambda: dependencies.rdap_client.query(domain=rdap_domain, servers=servers)

    deadline_expired = asyncio.Event()
    tasks = {
        check: asyncio.create_task(
            _run_check(
                check,
                domain,
                operation,
                analysis_id,
                task_id,
                progress_callback,
                observations,
                deadline_expired,
            )
        )
        for check, operation in operations.items()
    }
    done = await _wait_for_tasks(tasks, deadline, deadline_expired)

    for check, task in tasks.items():
        if task not in done and check not in observations:
            await _record_unstarted_timeout(
                check,
                domain,
                analysis_id,
                task_id,
                progress_callback,
                observations,
            )

    results: dict[str, object] = {}
    for check, task in tasks.items():
        if task not in done:
            results[check] = asyncio.TimeoutError()
            continue
        try:
            results[check] = task.result()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            results[check] = exc
    return results


def _get_rdap_result(results: dict[str, object], errors: list[AnalysisError]) -> RDAPResponse | None:
    raw_result = results.get('rdap')
    if raw_result is None:
        return None
    if isinstance(raw_result, asyncio.CancelledError):
        raise raw_result
    if isinstance(raw_result, asyncio.TimeoutError):
        errors.append(_analysis_error('rdap', timed_out=True))
        return None
    if isinstance(raw_result, RDAPResponse):
        return raw_result

    errors.append(_analysis_error('rdap'))
    return None


async def _lookup_geoip(
    ips: list[str],
    errors: list[AnalysisError],
    dependencies: DomainDependencies,
    deadline: float,
    domain: str,
    analysis_id: str | None,
    task_id: str | None,
    progress_callback: ProgressCallback | None,
    observations: dict[str, _CheckObservation],
) -> dict[str, GeoIPRecord]:
    started_at = perf_counter()
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        _record_observation(observations, 'geoip', started_at, 'timeout')
        errors.append(_analysis_error('geoip', timed_out=True))
        duration_seconds = perf_counter() - started_at
        duration_ms = round(duration_seconds * 1000, 2)
        record_analysis_check('geoip', 'timeout', duration_seconds)
        logger.info(
            'domain analysis check completed',
            extra={
                'domain': domain,
                'check': 'geoip',
                'analysis_id': analysis_id,
                'task_id': task_id,
                'check_status': 'timeout',
                'check_duration_ms': duration_ms,
            },
        )
        await _report_progress(progress_callback, 'geoip', 'failed', duration_ms)
        return {}

    progress_status = 'successful'
    metric_status = 'success'
    observation_status: CheckObservationStatus = 'successful'
    await _report_progress(progress_callback, 'geoip', 'running')
    try:
        return await asyncio.wait_for(dependencies.geoip_service.lookup(ips=ips), timeout=remaining)
    except asyncio.TimeoutError:
        progress_status = 'failed'
        metric_status = 'timeout'
        observation_status = 'timeout'
        errors.append(_analysis_error('geoip', timed_out=True))
        return {}
    except asyncio.CancelledError:
        progress_status = 'failed'
        metric_status = 'cancelled'
        observation_status = 'cancelled'
        raise
    except Exception:
        progress_status = 'failed'
        metric_status = 'failed'
        observation_status = 'failed'
        errors.append(_analysis_error('geoip'))
        return {}
    finally:
        duration_seconds = perf_counter() - started_at
        _record_observation(observations, 'geoip', started_at, observation_status)
        record_analysis_check('geoip', metric_status, duration_seconds)
        logger.info(
            'domain analysis check completed',
            extra={
                'domain': domain,
                'check': 'geoip',
                'analysis_id': analysis_id,
                'task_id': task_id,
                'check_status': metric_status,
                'check_duration_ms': round(duration_seconds * 1000, 2),
            },
        )
        await _report_progress(progress_callback, 'geoip', progress_status, round(duration_seconds * 1000, 2))


class DomainService:
    def __init__(self, dependencies: DomainDependencies | None = None):
        self.dependencies = dependencies or DomainDependencies()

    async def analyze(
        self,
        domain: str,
        analysis_id: str | None = None,
        task_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> DomainSchema:
        started_at = perf_counter()
        analysis_status = 'failed'
        try:
            result = await self._analyze(
                domain,
                analysis_id=analysis_id,
                task_id=task_id,
                progress_callback=progress_callback,
            )
            analysis_status = 'partial' if result.analysis_errors else 'success'
            return result
        except AnalysisTimeoutError:
            analysis_status = 'timeout'
            raise
        except asyncio.CancelledError:
            analysis_status = 'cancelled'
            raise
        finally:
            record_analysis(analysis_status, perf_counter() - started_at)

    async def _analyze(
        self,
        domain: str,
        analysis_id: str | None = None,
        task_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> DomainSchema:
        started_at = perf_counter()
        started_at_utc = datetime.now(timezone.utc)
        deadline = asyncio.get_running_loop().time() + settings.ANALYSIS_TIMEOUT_SECONDS
        try:
            domain = validate_domain(domain=domain)
        except ValueError as e:
            raise DomainValidationError(str(e)) from e

        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise AnalysisTimeoutError('The domain analysis deadline was exceeded.')
        try:
            target_ips = await asyncio.wait_for(
                self.dependencies.network_guard.resolve_public_ips(domain),
                timeout=remaining,
            )
        except asyncio.TimeoutError as exc:
            raise AnalysisTimeoutError('The domain analysis deadline was exceeded.') from exc

        logger.info(
            'domain analysis started',
            extra={
                'domain': domain,
                'analysis_id': analysis_id,
                'task_id': task_id,
                'deadline_ms': round(settings.ANALYSIS_TIMEOUT_SECONDS * 1000, 2),
            },
        )
        errors: list[AnalysisError] = []
        observations: dict[str, _CheckObservation] = {}
        for check in ANALYSIS_CHECKS:
            await _report_progress(progress_callback, check, 'queued')

        servers, rdap_domain = await _load_rdap_context(
            domain,
            errors,
            self.dependencies,
            deadline,
            analysis_id,
            task_id,
            progress_callback,
            observations,
        )
        raw_results = await _collect_results(
            domain,
            target_ips,
            servers,
            rdap_domain,
            self.dependencies,
            deadline,
            analysis_id,
            task_id,
            progress_callback,
            observations,
        )

        rdap_result = _get_rdap_result(raw_results, errors)
        dns_result = _result_or_default(raw_results, 'dns', DNSRecords, DNSRecords(), errors)
        propagation_result = _result_or_default(raw_results, 'dns_propagation', PropagationSchema, None, errors)
        http_result = _result_or_default(raw_results, 'http', HTTPSchema, None, errors)
        ssl_result = _result_or_default(raw_results, 'ssl', SSLSchema, None, errors)
        ports_result = _result_or_default(raw_results, 'ports', PortsSchema, None, errors)
        latency_result = _result_or_default(raw_results, 'latency', LatencySchema, None, errors)

        all_ips = (dns_result.A + dns_result.AAAA)[: settings.MAX_GEOIP_IPS]
        geoip_result = await _lookup_geoip(
            ips=all_ips,
            errors=errors,
            dependencies=self.dependencies,
            deadline=deadline,
            domain=domain,
            analysis_id=analysis_id,
            task_id=task_id,
            progress_callback=progress_callback,
            observations=observations,
        )

        dns_schema = DNSSchema(
            A=dns_result.A,
            AAAA=dns_result.AAAA,
            MX=dns_result.MX,
            TXT=dns_result.TXT,
            CNAME=dns_result.CNAME,
            NS=dns_result.NS,
            SOA=dns_result.SOA,
            CAA=dns_result.CAA,
            PTR=dns_result.PTR,
            propagation=propagation_result,
        )

        completed_at = datetime.now(timezone.utc)
        result = DomainSchema(
            domain=domain,
            rdap_server=rdap_result.server if rdap_result else None,
            status=rdap_result.status if rdap_result else [],
            nameservers=rdap_result.nameservers if rdap_result else [],
            registrar=rdap_result.registrar if rdap_result else None,
            registration_date=rdap_result.registration_date if rdap_result else None,
            expiration_date=rdap_result.expiration_date if rdap_result else None,
            updated_date=rdap_result.updated_date if rdap_result else None,
            whois_server=rdap_result.whois_server if rdap_result else None,
            dns=dns_schema,
            geoip=geoip_result,
            http=http_result,
            ssl=ssl_result,
            ports=ports_result,
            latency=latency_result,
            metadata=_build_analysis_metadata(
                started_at=started_at_utc,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                domain=domain,
                observations=observations,
                rdap_result=rdap_result,
            ),
            analysis_errors=errors,
        )
        logger.info(
            'domain analysis completed',
            extra={
                'domain': domain,
                'analysis_id': analysis_id,
                'task_id': task_id,
                'error_count': len(errors),
                'analysis_duration_ms': round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return result
