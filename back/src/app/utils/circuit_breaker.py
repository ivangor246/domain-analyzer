import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.core.config import settings

T = TypeVar('T')
FailurePredicate = Callable[[Exception], bool]


class CircuitOpenError(RuntimeError):
    """Raised when a provider is temporarily skipped after repeated failures."""


@dataclass
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int | None = None,
        reset_seconds: float | None = None,
    ) -> None:
        self.failure_threshold = (
            failure_threshold if failure_threshold is not None else settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.reset_seconds = reset_seconds if reset_seconds is not None else settings.CIRCUIT_BREAKER_RESET_SECONDS
        self._states: dict[str, _CircuitState] = {}
        self._lock = asyncio.Lock()

    async def _before_call(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            state = self._states.get(key)
            if state is None or state.opened_at is None:
                return
            if now - state.opened_at < self.reset_seconds:
                raise CircuitOpenError(f'Circuit is open for provider {key}.')
            if state.probe_in_flight:
                raise CircuitOpenError(f'Circuit probe is already running for provider {key}.')
            state.probe_in_flight = True

    async def _record_success(self, key: str) -> None:
        async with self._lock:
            self._states.pop(key, None)

    async def _record_failure(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            state = self._states.setdefault(key, _CircuitState())
            state.failures += 1
            state.probe_in_flight = False
            if state.opened_at is not None or state.failures >= self.failure_threshold:
                state.opened_at = now

    async def _release_probe(self, key: str) -> None:
        async with self._lock:
            state = self._states.get(key)
            if state is not None:
                state.probe_in_flight = False

    async def call(
        self,
        key: str,
        operation: Callable[[], Awaitable[T]],
        should_trip: FailurePredicate | None = None,
    ) -> T:
        await self._before_call(key)
        try:
            result = await operation()
        except asyncio.CancelledError:
            await self._release_probe(key)
            raise
        except Exception as exc:
            if should_trip is None or should_trip(exc):
                await self._record_failure(key)
            else:
                await self._record_success(key)
            raise
        await self._record_success(key)
        return result

    async def reset(self) -> None:
        async with self._lock:
            self._states.clear()

    async def is_open(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            state = self._states.get(key)
            return state is not None and state.opened_at is not None and now - state.opened_at < self.reset_seconds
