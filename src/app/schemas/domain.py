from pydantic import Field

from .base import BaseSchema


class DomainSchema(BaseSchema):
    domain: str = Field(..., description='Normalized domain in punycode')
    rdap_servers: list[str] = Field(..., description="RDAP servers for the domain's TLD")
