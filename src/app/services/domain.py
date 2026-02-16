from app.core.exceptions import DomainValidationError
from app.schemas.domain import DomainSchema
from app.utils.domain_validator import validate_domain

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

        rdap = await RDAPClient.query(domain=domain, servers=servers)

        return DomainSchema(
            domain=domain,
            rdap_server=rdap.server,
            status=rdap.status,
            nameservers=rdap.nameservers,
            registrar=rdap.registrar,
            registration_date=rdap.registration_date,
            expiration_date=rdap.expiration_date,
            updated_date=rdap.updated_date,
            whois_server=rdap.whois_server,
        )
