from typing import Literal

from pydantic import Field

from .base import BaseSchema


class PortResult(BaseSchema):
    port: int = Field(..., description='Port number')
    open: bool = Field(..., description='True if the port accepted a TCP connection')
    status: Literal['open', 'closed', 'filtered'] = Field(
        ...,
        description=(
            'open — connection accepted; '
            'closed — connection actively refused (RST); '
            'filtered — no response within timeout (firewall / packet drop)'
        ),
    )
    service: str | None = Field(None, description='Well-known service name for this port')


class PortsSchema(BaseSchema):
    results: list[PortResult] = Field(default_factory=list, description='Scan result per port')
