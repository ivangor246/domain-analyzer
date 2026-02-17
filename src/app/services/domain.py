import asyncio

from app.core.exceptions import DomainValidationError
from app.schemas.dns import DNSSchema
from app.schemas.domain import DomainSchema
from app.utils.domain_validator import validate_domain

from .dns_resolver import DNSResolver
from .rdap_bootstrap import RDAPBootstrap
from .rdap_client import RDAPClient


class DomainService:
    async def analyze(self, domain: str) -> DomainSchema:
        try:
            domain = validate_domain(domain=domain)
            bootstrap = await RDAPBootstrap.get_instance()
            servers = bootstrap.get_servers(domain=domain)
        except ValueError as e:
            raise DomainValidationError(str(e))

        rdap_result, dns_result = await asyncio.gather(
            RDAPClient.query(domain=domain, servers=servers),
            DNSResolver.resolve(domain=domain),
        )

        dns_data = dns_result
        dns_schema = DNSSchema(
            A=dns_data.A,
            AAAA=dns_data.AAAA,
            MX=dns_data.MX,
            TXT=dns_data.TXT,
            CNAME=dns_data.CNAME,
            NS=dns_data.NS,
            SOA=dns_data.SOA,
            CAA=dns_data.CAA,
            PTR=dns_data.PTR,
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
        )
