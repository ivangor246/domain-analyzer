import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int | None = None


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
