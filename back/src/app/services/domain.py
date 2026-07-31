import asyncio
from typing import Any, Awaitable, TypeVar

from app.core.exceptions import DomainValidationError
from app.schemas.dns import DNSSchema, PropagationSchema
from app.schemas.domain import AnalysisError, DomainSchema
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
from .port_scanner import PortScanner
from .rdap_bootstrap import RDAPBootstrap
from .rdap_client import RDAPClient, RDAPResponse
from .ssl_cert import SSLCertService

T = TypeVar('T')

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


def _analysis_error(check: str) -> AnalysisError:
    code, message = _ANALYSIS_FAILURES[check]
    return AnalysisError(check=check, code=code, message=message)


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
    if not isinstance(result, expected_type):
        errors.append(_analysis_error(check))
        return default
    return result


async def _load_rdap_context(domain: str, errors: list[AnalysisError]) -> tuple[list[str], str]:
    try:
        bootstrap = await RDAPBootstrap.get_instance()
        servers, rdap_domain = bootstrap.get_servers(domain=domain)
        if servers:
            return servers, rdap_domain
    except asyncio.CancelledError:
        raise
    except Exception:
        pass

    errors.append(_analysis_error('rdap'))
    return [], domain


async def _collect_results(domain: str, servers: list[str], rdap_domain: str) -> dict[str, object]:
    tasks: dict[str, Awaitable[Any]] = {
        'dns': DNSResolver.resolve(domain=domain),
        'dns_propagation': DNSPropagation.check(domain=domain),
        'http': HTTPHeadersService.probe(domain=domain),
        'ssl': SSLCertService.check(domain=domain),
        'ports': PortScanner.scan(host=domain),
        'latency': LatencyService.measure(host=domain),
    }
    if servers:
        tasks['rdap'] = RDAPClient.query(domain=rdap_domain, servers=servers)

    return dict(zip(tasks, await asyncio.gather(*tasks.values(), return_exceptions=True)))


def _get_rdap_result(results: dict[str, object], errors: list[AnalysisError]) -> RDAPResponse | None:
    raw_result = results.get('rdap')
    if raw_result is None:
        return None
    if isinstance(raw_result, asyncio.CancelledError):
        raise raw_result
    if isinstance(raw_result, RDAPResponse):
        return raw_result

    errors.append(_analysis_error('rdap'))
    return None


async def _lookup_geoip(ips: list[str], errors: list[AnalysisError]) -> dict[str, GeoIPRecord]:
    try:
        return await GeoIPService.lookup(ips=ips)
    except asyncio.CancelledError:
        raise
    except Exception:
        errors.append(_analysis_error('geoip'))
        return {}


class DomainService:
    async def analyze(self, domain: str) -> DomainSchema:
        try:
            domain = validate_domain(domain=domain)
        except ValueError as e:
            raise DomainValidationError(str(e)) from e

        errors: list[AnalysisError] = []
        servers, rdap_domain = await _load_rdap_context(domain, errors)
        raw_results = await _collect_results(domain, servers, rdap_domain)

        rdap_result = _get_rdap_result(raw_results, errors)
        dns_result = _result_or_default(raw_results, 'dns', DNSRecords, DNSRecords(), errors)
        propagation_result = _result_or_default(raw_results, 'dns_propagation', PropagationSchema, None, errors)
        http_result = _result_or_default(raw_results, 'http', HTTPSchema, None, errors)
        ssl_result = _result_or_default(raw_results, 'ssl', SSLSchema, None, errors)
        ports_result = _result_or_default(raw_results, 'ports', PortsSchema, None, errors)
        latency_result = _result_or_default(raw_results, 'latency', LatencySchema, None, errors)

        all_ips = dns_result.A + dns_result.AAAA
        geoip_result = await _lookup_geoip(ips=all_ips, errors=errors)

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

        return DomainSchema(
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
            analysis_errors=errors,
        )
