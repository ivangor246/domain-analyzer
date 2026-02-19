import asyncio

from app.core.exceptions import DomainValidationError
from app.schemas.dns import DNSSchema
from app.schemas.domain import DomainSchema
from app.utils.domain_validator import validate_domain

from .dns_propagation import DNSPropagation
from .dns_resolver import DNSResolver
from .geoip import GeoIPService
from .http_headers import HTTPHeadersService
from .rdap_bootstrap import RDAPBootstrap
from .rdap_client import RDAPClient
from .port_scanner import PortScanner
from .ssl_cert import SSLCertService


class DomainService:
    async def analyze(self, domain: str) -> DomainSchema:
        try:
            domain = validate_domain(domain=domain)
            bootstrap = await RDAPBootstrap.get_instance()
            servers, rdap_domain = bootstrap.get_servers(domain=domain)
        except ValueError as e:
            raise DomainValidationError(str(e))

        rdap_result, dns_result, propagation_result, http_result, ssl_result, ports_result = await asyncio.gather(
            RDAPClient.query(domain=rdap_domain, servers=servers),
            DNSResolver.resolve(domain=domain),
            DNSPropagation.check(domain=domain),
            HTTPHeadersService.probe(domain=domain),
            SSLCertService.check(domain=domain),
            PortScanner.scan(host=domain),
        )

        all_ips = dns_result.A + dns_result.AAAA
        geoip_result = await GeoIPService.lookup(ips=all_ips)

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
            rdap_server=rdap_result.server,
            status=rdap_result.status,
            nameservers=rdap_result.nameservers,
            registrar=rdap_result.registrar,
            registration_date=rdap_result.registration_date,
            expiration_date=rdap_result.expiration_date,
            updated_date=rdap_result.updated_date,
            whois_server=rdap_result.whois_server,
            dns=dns_schema,
            geoip=geoip_result,
            http=http_result,
            ssl=ssl_result,
            ports=ports_result,
        )
