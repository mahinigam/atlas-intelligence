import logging
from collections.abc import AsyncIterator

from fastapi import Depends, Request
import httpx

from app.cache import CacheClient
from app.config import get_settings

logger = logging.getLogger(__name__)


async def get_http_client(request: Request) -> AsyncIterator[httpx.AsyncClient]:
    client = getattr(request.app.state, "client", None)
    if client is not None:
        yield client
        return

    logger.warning("App HTTP client missing from lifespan state; creating request-scoped fallback client")
    async with httpx.AsyncClient(timeout=40.0) as fallback_client:
        yield fallback_client


async def get_redis():
    """Return a Redis client, or None if Redis is unreachable."""
    settings = get_settings()
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        try:
            yield redis
        finally:
            await redis.close()
    except Exception:
        logger.warning("Redis unavailable at %s — running without cache", settings.redis_url)
        yield None


async def get_cache(redis=Depends(get_redis)) -> CacheClient:
    settings = get_settings()
    return CacheClient(redis_client=redis, ttl_seconds=settings.cache_ttl_seconds)
