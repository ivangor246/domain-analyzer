import asyncio
import time
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar('K', bound=Hashable)
T = TypeVar('T')


@dataclass(frozen=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class AsyncTTLCache(Generic[K, T]):
    """A bounded, process-local cache with explicit expiration for safe provider data."""

    def __init__(self, max_entries: int) -> None:
        if max_entries <= 0:
            raise ValueError('max_entries must be greater than zero')
        self.max_entries = max_entries
        self._entries: dict[K, _CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: K) -> T | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    async def set(self, key: K, value: T, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            await self.delete(key)
            return

        now = time.monotonic()
        async with self._lock:
            self._remove_expired(now)
            if key not in self._entries and len(self._entries) >= self.max_entries:
                oldest_key = min(self._entries, key=lambda item: self._entries[item].expires_at)
                self._entries.pop(oldest_key, None)
            self._entries[key] = _CacheEntry(value=value, expires_at=now + ttl_seconds)

    async def delete(self, key: K) -> None:
        async with self._lock:
            self._entries.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()

    def _remove_expired(self, now: float) -> None:
        expired_keys = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)
