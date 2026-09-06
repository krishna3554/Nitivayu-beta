"""Tolerant Redis client: cache, OTP/session store, rate limiting, SSE fan-out.

Returns None when REDIS_URL is unset or Redis is unreachable — every caller
must degrade gracefully (memory fallback or skip caching). Never raise here.
"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache
def get_redis():
    """Process-wide client, or None. Safe to call on every request."""
    try:
        from app.config import get_settings
    except Exception:  # pragma: no cover - import-time safety
        return None
    url = get_settings().REDIS_URL.strip()
    if not url:
        return None
    try:
        import redis.asyncio as redis

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        return client
    except Exception:
        logger.warning("Redis client init failed; running without Redis", exc_info=True)
        return None


async def ping() -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        await client.ping()
        return True
    except Exception:
        return False
