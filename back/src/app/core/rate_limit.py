import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import inspect
import math
from threading import Lock
import time
from uuid import uuid4

from app.core.config import settings
from app.core.exceptions import RateLimitUnavailableError


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int | None = None


_REDIS_RATE_LIMIT_SCRIPT = """
local server_time = redis.call('TIME')
local now_ms = tonumber(server_time[1]) * 1000 + math.floor(tonumber(server_time[2]) / 1000)
local window_ms = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local cutoff_ms = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff_ms)
local count = redis.call('ZCARD', KEYS[1])

if count >= max_requests then
    local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry_after_ms = tonumber(first[2]) + window_ms - now_ms
    return {0, 0, math.max(1, math.ceil(retry_after_ms / 1000))}
end

redis.call('ZADD', KEYS[1], now_ms, ARGV[3])
redis.call('EXPIRE', KEYS[1], math.max(1, math.ceil(window_ms / 1000)))
return {1, math.max(0, max_requests - count - 1), 0}
"""


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, clock: Callable[[], float] | None = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> RateLimitResult:
        now = self._clock()
        cutoff = now - self.window_seconds

        async with self._lock:
            for stored_key, timestamps in tuple(self._requests.items()):
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps:
                    del self._requests[stored_key]

            timestamps = self._requests.setdefault(key, deque())

            if len(timestamps) >= self.max_requests:
                retry_after = max(1, math.ceil(timestamps[0] + self.window_seconds - now))
                return RateLimitResult(allowed=False, remaining=0, retry_after=retry_after)

            timestamps.append(now)
            return RateLimitResult(
                allowed=True,
                remaining=self.max_requests - len(timestamps),
            )


class RedisRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, fallback: RateLimiter | None = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fallback = fallback
        self._client: object | None = None
        self._client_lock = Lock()

    @staticmethod
    def _key(client_key: str) -> str:
        digest = hashlib.sha256(client_key.encode('utf-8')).hexdigest()
        return f'domain_analyzer:rate_limit:{digest}'

    def _get_client(self):
        with self._client_lock:
            if self._client is None:
                from redis.asyncio import Redis

                self._client = Redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
                )
            return self._client

    async def _check_async(self, client_key: str) -> RateLimitResult:
        values = self._get_client().eval(
            _REDIS_RATE_LIMIT_SCRIPT,
            1,
            self._key(client_key),
            round(self.window_seconds * 1000),
            self.max_requests,
            uuid4().hex,
        )
        if inspect.isawaitable(values):
            values = await values
        try:
            allowed = bool(int(values[0]))
            remaining = max(0, int(values[1]))
            retry_after = max(1, int(values[2])) if not allowed else None
        except (IndexError, TypeError, ValueError) as exc:
            raise RuntimeError('Redis returned an invalid rate-limit response') from exc
        return RateLimitResult(allowed=allowed, remaining=remaining, retry_after=retry_after)

    async def check(self, client_key: str) -> RateLimitResult:
        try:
            return await self._check_async(client_key)
        except Exception as exc:
            if self.fallback is not None:
                return await self.fallback.check(client_key)
            raise RateLimitUnavailableError('The Redis rate limiter is unavailable.') from exc
