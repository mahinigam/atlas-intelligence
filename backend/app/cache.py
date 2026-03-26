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

    # ── Time-Series Append / Retrieve ─────────────────────────────────────
    # Used for persisting provider metrics, country quality snapshots, etc.

    async def append_to_list(
        self, key: str, value: dict[str, Any], *, max_length: int = 500
    ) -> None:
        """Append a JSON-serialized entry to a Redis list, trimming to max_length."""
        if self.redis is None:
            return
        try:
            await self.redis.rpush(key, json.dumps(value, default=str))
            await self.redis.ltrim(key, -max_length, -1)
        except Exception:
            logger.warning("Redis RPUSH failed for key %s", key)

    async def get_list(
        self, key: str, count: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve recent entries from a Redis list (newest last)."""
        if self.redis is None:
            return []
        try:
            raw = await self.redis.lrange(key, -count, -1)
            return [json.loads(entry) for entry in raw]
        except Exception:
            logger.warning("Redis LRANGE failed for key %s", key)
            return []

    async def list_length(self, key: str) -> int:
        """Return the length of a Redis list key."""
        if self.redis is None:
            return 0
        try:
            return await self.redis.llen(key) or 0
        except Exception:
            return 0
