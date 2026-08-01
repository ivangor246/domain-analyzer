import asyncio
import socket
import time

from app.core.config import settings
from app.schemas.latency import LatencyResult, LatencySchema


class LatencyService:
    @staticmethod
    async def measure(host: str) -> LatencySchema:
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            ip = infos[0][4][0]
        except Exception:
            ip = host

        tcp_80, tcp_443 = await asyncio.gather(
            LatencyService._probe(ip, 80),
            LatencyService._probe(ip, 443),
        )
        return LatencySchema(tcp_80=tcp_80, tcp_443=tcp_443)

    @staticmethod
    async def _probe(ip: str, port: int) -> LatencyResult | None:
        tasks = [LatencyService._tcp_connect_ms(ip, port) for _ in range(settings.LATENCY_PROBES)]
        raw: list[int | None] = list(await asyncio.gather(*tasks))

        times = [t for t in raw if t is not None]
        loss = settings.LATENCY_PROBES - len(times)

        if not times:
            return None

        return LatencyResult(
            min_ms=min(times),
            avg_ms=int(sum(times) / len(times)),
            max_ms=max(times),
            loss=loss,
        )

    @staticmethod
    async def _tcp_connect_ms(ip: str, port: int) -> int | None:
        start = time.perf_counter()
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=settings.LATENCY_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return elapsed_ms
        except Exception:
            return None
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
