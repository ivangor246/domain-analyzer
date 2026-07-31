import asyncio
import socket

from app.schemas.ports import PortResult, PortsSchema

_TIMEOUT = 3

_PORTS: dict[int, str] = {
    21: 'FTP',
    22: 'SSH',
    25: 'SMTP',
    80: 'HTTP',
    110: 'POP3',
    143: 'IMAP',
    443: 'HTTPS',
    587: 'SMTP Submission',
    3306: 'MySQL',
    5432: 'PostgreSQL',
    8080: 'HTTP Alt',
    8443: 'HTTPS Alt',
}


class PortScanner:
    @staticmethod
    async def scan(host: str) -> PortsSchema:
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            target = infos[0][4][0]
        except Exception:
            target = host

        tasks = [PortScanner._check_port(target, port) for port in _PORTS]
        results: list[PortResult] = list(await asyncio.gather(*tasks))
        return PortsSchema(results=results)

    @staticmethod
    async def _check_port(host: str, port: int) -> PortResult:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
            return PortResult(port=port, open=True, status='open', service=_PORTS.get(port))
        except (asyncio.TimeoutError, TimeoutError):
            return PortResult(port=port, open=False, status='filtered', service=_PORTS.get(port))
        except (ConnectionRefusedError, OSError):
            return PortResult(port=port, open=False, status='closed', service=_PORTS.get(port))
