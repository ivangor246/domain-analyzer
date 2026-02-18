from typing import Literal

from pydantic import Field

from .base import BaseSchema


class PropagationServerSchema(BaseSchema):
    name: str = Field(..., description='DNS server name')
    ip: str = Field(..., description='DNS server IP address')
    A: list[str] = Field(default_factory=list, description='IPv4 addresses returned by this server')
    AAAA: list[str] = Field(default_factory=list, description='IPv6 addresses returned by this server')
    status: Literal['ok', 'timeout', 'error'] = Field(..., description='Query status')


class PropagationSchema(BaseSchema):
    consistent: bool = Field(..., description='True if all servers return the same records')
    servers: list[PropagationServerSchema] = Field(default_factory=list, description='Per-server results')


class MXRecord(BaseSchema):
    priority: int = Field(..., description='MX priority value')
    exchange: str = Field(..., description='Mail server hostname')


class SOARecord(BaseSchema):
    mname: str = Field(..., description='Primary nameserver')
    rname: str = Field(..., description='Responsible person email (dot-notation)')
    serial: int = Field(..., description='Zone serial number')
    refresh: int = Field(..., description='Refresh interval in seconds')
    retry: int = Field(..., description='Retry interval in seconds')
    expire: int = Field(..., description='Expiry time in seconds')
    minimum: int = Field(..., description='Minimum TTL in seconds')


class CAARecord(BaseSchema):
    flags: int = Field(..., description='CAA record flags')
    tag: str = Field(..., description='CAA tag (issue, issuewild, iodef)')
    value: str = Field(..., description='CAA value')


class DNSSchema(BaseSchema):
    A: list[str] = Field(default_factory=list, description='IPv4 addresses')
    AAAA: list[str] = Field(default_factory=list, description='IPv6 addresses')
    MX: list[MXRecord] = Field(default_factory=list, description='Mail exchange records')
    TXT: list[str] = Field(default_factory=list, description='TXT records')
    CNAME: list[str] = Field(default_factory=list, description='Canonical name records')
    NS: list[str] = Field(default_factory=list, description='Nameserver records')
    SOA: SOARecord | None = Field(None, description='Start of authority record')
    CAA: list[CAARecord] = Field(default_factory=list, description='Certificate authority authorization records')
    PTR: dict[str, str | None] = Field(default_factory=dict, description='Reverse DNS (IP to hostname mapping)')
    propagation: PropagationSchema | None = Field(None, description='DNS propagation check across public resolvers')
