from pydantic import Field

from .base import BaseSchema


class LatencyResult(BaseSchema):
    min_ms: int = Field(..., description='Minimum TCP connect time across probes in milliseconds')
    avg_ms: int = Field(..., description='Average TCP connect time across probes in milliseconds')
    max_ms: int = Field(..., description='Maximum TCP connect time across probes in milliseconds')
    loss: int = Field(..., description='Number of failed probes out of total sent')


class LatencySchema(BaseSchema):
    tcp_80: LatencyResult | None = Field(None, description='TCP latency to port 80 (pure network, no HTTP)')
    tcp_443: LatencyResult | None = Field(None, description='TCP latency to port 443 (pure network, no TLS)')
