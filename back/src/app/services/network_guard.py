import asyncio
import ipaddress
import socket

from app.core.exceptions import TargetNotAllowedError

_RESOLUTION_TIMEOUT = 5


class NetworkTargetGuard:
    @staticmethod
    def is_public_ip(address: str) -> bool:
        try:
            return ipaddress.ip_address(address).is_global
        except ValueError:
            return False

    @staticmethod
    async def validate(host: str) -> None:
        loop = asyncio.get_running_loop()

        try:
            addresses = await asyncio.wait_for(
                loop.getaddrinfo(host, None, type=socket.SOCK_STREAM),
                timeout=_RESOLUTION_TIMEOUT,
            )
        except asyncio.CancelledError:
            raise
        except (OSError, asyncio.TimeoutError) as e:
            raise TargetNotAllowedError('Domain must resolve to a public IP address.') from e

        resolved_ips = {address[4][0] for address in addresses if address[4]}
        if not resolved_ips or any(not NetworkTargetGuard.is_public_ip(ip) for ip in resolved_ips):
            raise TargetNotAllowedError('Domain must resolve only to public IP addresses.')
