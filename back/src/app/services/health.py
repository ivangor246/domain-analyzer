import asyncio

from app.core.config import settings

_WORKER_PING_TIMEOUT_MARGIN_SECONDS = 1.0


async def check_redis() -> bool:
    client = None
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
        )
        await asyncio.wait_for(client.ping(), timeout=settings.REDIS_TIMEOUT_SECONDS)
        return True
    except Exception:
        return False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


def _ping_worker_sync() -> bool:
    from app.core.celery_app import celery_app

    inspect_timeout = max(
        0.1,
        settings.REDIS_TIMEOUT_SECONDS - _WORKER_PING_TIMEOUT_MARGIN_SECONDS,
    )
    replies = celery_app.control.inspect(timeout=inspect_timeout).ping()
    return bool(replies)


async def check_worker() -> bool:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_ping_worker_sync),
            timeout=settings.REDIS_TIMEOUT_SECONDS,
        )
        return bool(result)
    except Exception:
        return False


async def check_dependencies() -> dict[str, bool]:
    results = await asyncio.gather(check_redis(), check_worker(), return_exceptions=True)
    return {
        'redis': results[0] is True,
        'worker': results[1] is True,
    }
