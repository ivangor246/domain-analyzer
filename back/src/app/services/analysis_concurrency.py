from collections.abc import Awaitable, Callable
from threading import Lock
from typing import TypeVar

from app.core.config import settings

_CONCURRENCY_KEY = 'domain_analyzer:analysis_concurrency'

_ACQUIRE_SCRIPT = """
local server_time = redis.call('TIME')
local now_ms = tonumber(server_time[1]) * 1000 + math.floor(tonumber(server_time[2]) / 1000)
local lease_ms = tonumber(ARGV[1])
local max_concurrency = tonumber(ARGV[2])
local member = ARGV[3]

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
local current = redis.call('ZSCORE', KEYS[1], member)
if current then
    redis.call('ZADD', KEYS[1], now_ms + lease_ms, member)
    redis.call('EXPIRE', KEYS[1], math.max(1, math.ceil(lease_ms / 1000) + 1))
    return 1
end

if redis.call('ZCARD', KEYS[1]) >= max_concurrency then
    return 0
end

redis.call('ZADD', KEYS[1], now_ms + lease_ms, member)
redis.call('EXPIRE', KEYS[1], math.max(1, math.ceil(lease_ms / 1000) + 1))
return 1
"""

_RELEASE_SCRIPT = """
return redis.call('ZREM', KEYS[1], ARGV[1])
"""

T = TypeVar('T')


class AnalysisConcurrencyBusyError(Exception): ...


class AnalysisConcurrencyUnavailableError(Exception): ...


class RedisAnalysisConcurrencyLimiter:
    def __init__(self, max_concurrency: int | None = None, lease_seconds: float | None = None) -> None:
        self.max_concurrency = max_concurrency if max_concurrency is not None else settings.ANALYSIS_MAX_CONCURRENCY
        self.lease_seconds = lease_seconds if lease_seconds is not None else settings.ANALYSIS_CONCURRENCY_LEASE_SECONDS
        self._client: object | None = None
        self._client_lock = Lock()

    async def _get_client(self):
        with self._client_lock:
            if self._client is None:
                from redis.asyncio import Redis

                self._client = Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
                )
            return self._client

    async def acquire(self, task_id: str) -> bool:
        try:
            client = await self._get_client()
            result = await client.eval(
                _ACQUIRE_SCRIPT,
                1,
                _CONCURRENCY_KEY,
                round(self.lease_seconds * 1000),
                self.max_concurrency,
                task_id,
            )
            return bool(int(result))
        except (TypeError, ValueError) as exc:
            raise AnalysisConcurrencyUnavailableError('Redis returned an invalid concurrency response.') from exc
        except Exception as exc:
            raise AnalysisConcurrencyUnavailableError('The Redis concurrency limiter is unavailable.') from exc

    async def release(self, task_id: str) -> None:
        try:
            client = await self._get_client()
            await client.eval(_RELEASE_SCRIPT, 1, _CONCURRENCY_KEY, task_id)
        except Exception as exc:
            raise AnalysisConcurrencyUnavailableError('The Redis concurrency limiter is unavailable.') from exc


async def run_with_concurrency_limit(
    task_id: str,
    operation: Callable[[], Awaitable[T]],
    limiter: RedisAnalysisConcurrencyLimiter | None = None,
) -> T:
    limiter = limiter or RedisAnalysisConcurrencyLimiter()
    acquired = await limiter.acquire(task_id)
    if not acquired:
        raise AnalysisConcurrencyBusyError('The configured analysis concurrency limit is currently full.')

    try:
        return await operation()
    finally:
        try:
            await limiter.release(task_id)
        except AnalysisConcurrencyUnavailableError:
            pass
