import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CacheClient:
    """Redis-backed cache with transparent no-op fallback when Redis is unavailable."""

    def __init__(self, redis_client: Any | None, ttl_seconds: int) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    async def get_json(self, key: str) -> dict[str, Any] | None:
        if self.redis is None:
            return None
        try:
            payload = await self.redis.get(key)
            if not payload:
                return None
            return json.loads(payload)
        except Exception:
            logger.warning("Redis GET failed for key %s, treating as cache miss", key)
            return None

    async def set_json(self, key: str, value: dict[str, Any]) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value, default=str), ex=self.ttl_seconds)
        except Exception:
            logger.warning("Redis SET failed for key %s, skipping cache write", key)
