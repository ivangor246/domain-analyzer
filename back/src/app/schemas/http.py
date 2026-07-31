from pydantic import Field

from .base import BaseSchema


class HTTPProbeResult(BaseSchema):
    reachable: bool = Field(..., description='Whether the server responded successfully')
    status_code: int | None = Field(None, description='HTTP response status code')
    final_url: str | None = Field(None, description='Final URL after all redirects')
    redirect_chain: list[str] = Field(default_factory=list, description='Intermediate redirect URLs')
    response_time_ms: int | None = Field(None, description='Time to first response in milliseconds')
    # Server identity
    server: str | None = Field(None, description='Server header (e.g. nginx/1.24)')
    x_powered_by: str | None = Field(None, description='X-Powered-By header (e.g. PHP/8.2)')
    via: str | None = Field(None, description='Via header (proxy / CDN info)')
    # Content
    content_type: str | None = Field(None, description='Content-Type header')
    cache_control: str | None = Field(None, description='Cache-Control header')
    # Security headers
    content_security_policy: str | None = Field(None, description='Content-Security-Policy header')
    strict_transport_security: str | None = Field(None, description='Strict-Transport-Security (HSTS) header')
    x_frame_options: str | None = Field(None, description='X-Frame-Options header')
    x_content_type_options: str | None = Field(None, description='X-Content-Type-Options header')
    referrer_policy: str | None = Field(None, description='Referrer-Policy header')
    permissions_policy: str | None = Field(None, description='Permissions-Policy header')


class HTTPSchema(BaseSchema):
    http: HTTPProbeResult | None = Field(None, description='Probe result for HTTP (port 80)')
    https: HTTPProbeResult | None = Field(None, description='Probe result for HTTPS (port 443)')
