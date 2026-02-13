from app.core.exceptions import DomainValidationError
from app.schemas.domain import DomainSchema
from app.utils.domain_validator import validate_domain

from .rdap_bootstrap import RDAPBootstrapService


class DomainService:
    async def analyze(self, domain: str) -> DomainSchema:
        try:
            domain = validate_domain(domain=domain)
            bootstrap = await RDAPBootstrapService.get_instance()
            servers = bootstrap.get_servers(domain=domain)
        except ValueError as e:
            raise DomainValidationError(str(e))

        return DomainSchema(
            domain=domain,
            rdap_servers=servers,
        )
