from datetime import datetime

from pydantic import Field

from .base import BaseSchema


class DomainSchema(BaseSchema):
    domain: str = Field(..., description='Normalized domain in punycode')
    rdap_server: str = Field(..., description='RDAP server used for query')
    status: list[str] = Field(default_factory=list, description='Domain status codes')
    nameservers: list[str] = Field(default_factory=list, description='Nameserver hostnames')
    registrar: str | None = Field(None, description='Registrar name')
    registration_date: datetime | None = Field(None, description='Domain registration date')
    expiration_date: datetime | None = Field(None, description='Domain expiration date')
    updated_date: datetime | None = Field(None, description='Last update date')
    whois_server: str | None = Field(None, description='WHOIS server hostname')
