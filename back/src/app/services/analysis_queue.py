import logging
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)

_QUEUE_KEY = 'domain_analyzer:analysis_queue'

_MARK_QUEUED_SCRIPT = """
local server_time = redis.call('TIME')
local now_seconds = tonumber(server_time[1])
local expires_at = now_seconds + tonumber(ARGV[1])
redis.call('ZADD', KEYS[1], expires_at, ARGV[2])
redis.call('EXPIRE', KEYS[1], math.max(1, tonumber(ARGV[1]) + 1))
return 1
"""

_REMOVE_SCRIPT = """
return redis.call('ZREM', KEYS[1], ARGV[1])
"""

_DEPTH_SCRIPT = """
local server_time = redis.call('TIME')
local now_seconds = tonumber(server_time[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_seconds)
return redis.call('ZCARD', KEYS[1])
"""


class RedisAnalysisQueueTracker:
    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.ANALYSIS_JOB_TTL_SECONDS
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

    async def mark_queued(self, analysis_id: str) -> None:
        client = await self._get_client()
        await client.eval(_MARK_QUEUED_SCRIPT, 1, _QUEUE_KEY, self.ttl_seconds, analysis_id)

    async def mark_started(self, analysis_id: str) -> None:
        client = await self._get_client()
        await client.eval(_REMOVE_SCRIPT, 1, _QUEUE_KEY, analysis_id)

    async def remove(self, analysis_id: str) -> None:
        await self.mark_started(analysis_id)

    async def depth(self) -> int:
        client = await self._get_client()
        result = await client.eval(_DEPTH_SCRIPT, 1, _QUEUE_KEY)
        return int(result)


queue_tracker = RedisAnalysisQueueTracker()


async def mark_analysis_queued(analysis_id: str) -> None:
    try:
        await queue_tracker.mark_queued(analysis_id)
    except Exception:
        logger.warning('analysis queue depth tracking failed', extra={'operation': 'mark_queued'})


async def mark_analysis_started(analysis_id: str) -> None:
    try:
        await queue_tracker.mark_started(analysis_id)
    except Exception:
        logger.warning('analysis queue depth tracking failed', extra={'operation': 'mark_started'})


async def remove_analysis_from_queue(analysis_id: str) -> None:
    try:
        await queue_tracker.remove(analysis_id)
    except Exception:
        logger.warning('analysis queue depth tracking failed', extra={'operation': 'remove'})
