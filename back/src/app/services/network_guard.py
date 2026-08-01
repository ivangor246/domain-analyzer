import asyncio
import ipaddress
import socket

from app.core.exceptions import TargetNotAllowedError
from app.core.config import settings


class NetworkTargetGuard:
    @staticmethod
    def is_public_ip(address: str) -> bool:
        try:
            return ipaddress.ip_address(address).is_global
        except ValueError:
            return False

    @staticmethod
    async def resolve_public_ips(host: str) -> list[str]:
        loop = asyncio.get_running_loop()

        try:
            addresses = await asyncio.wait_for(
                loop.getaddrinfo(host, None, type=socket.SOCK_STREAM),
                timeout=settings.NETWORK_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            raise
        except (OSError, asyncio.TimeoutError) as e:
            raise TargetNotAllowedError('Domain must resolve to a public IP address.') from e

        resolved_ips: list[str] = []
        for address in addresses:
            if len(address) <= 4 or not address[4] or not address[4][0]:
                continue
            ip = address[4][0]
            if ip not in resolved_ips:
                resolved_ips.append(ip)
        if not resolved_ips or any(not NetworkTargetGuard.is_public_ip(ip) for ip in resolved_ips):
            raise TargetNotAllowedError('Domain must resolve only to public IP addresses.')

        return resolved_ips

    @staticmethod
    async def validate(host: str) -> None:
        await NetworkTargetGuard.resolve_public_ips(host)
