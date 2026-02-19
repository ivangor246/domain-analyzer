from datetime import datetime

from pydantic import Field

from .base import BaseSchema
from .dns import DNSSchema
from .geoip import GeoIPRecord
from .http import HTTPSchema
from .latency import LatencySchema
from .ports import PortsSchema
from .ssl import SSLSchema


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
    dns: DNSSchema = Field(default_factory=DNSSchema, description='DNS records')
    geoip: dict[str, GeoIPRecord] = Field(default_factory=dict, description='GeoIP / ASN data keyed by IP address')
    http: HTTPSchema | None = Field(None, description='HTTP / HTTPS probe results with response headers')
    ssl: SSLSchema | None = Field(None, description='SSL/TLS certificate and connection details')
    ports: PortsSchema | None = Field(None, description='TCP port scan results for common service ports')
    latency: LatencySchema | None = Field(None, description='TCP latency probes to port 80 and 443 (min/avg/max/loss)')
