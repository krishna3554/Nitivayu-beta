"""Workspace-aware rate limiting: Redis counters with an in-memory fallback.

Keyed per client IP (and user when authenticated) on /auth/* and
/submissions — auth makes limiting *more* effective since abuse can be
keyed to a real account, not just an IP (§5.8).
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_user_optional
from app.services import redis_client as redis_mod

_memory_hits: dict[str, deque] = defaultdict(deque)
_MEMORY_WINDOW = 120  # seconds of history retained per key


def _client_key(request: Request, user: dict | None) -> str:
    ip = request.client.host if request.client else "unknown"
    who = (user or {}).get("user_id") or ip
    return f"{who}:{ip}"


async def _allow_redis(key: str, limit: int, window: int) -> bool:
    client = redis_mod.get_redis()
    if client is None:
        return True  # fall through to memory counting below
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window)
        return count <= limit
    except Exception:
        return True


def _allow_memory(key: str, limit: int, window: int) -> bool:
    now = time.monotonic()
    hits = _memory_hits[key]
    while hits and hits[0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        return False
    hits.append(now)
    # Opportunistic pruning to bound process memory.
    if len(_memory_hits) > 10000:
        _memory_hits.clear()
    return True


def rate_limit(limit: int | None = None, window_seconds: int = 60, *, setting: str = "RATE_LIMIT_AUTH_PER_MIN"):
    """Dependency factory. `limit` overrides the settings key when given."""
    async def checker(request: Request, user: dict | None = Depends(get_current_user_optional)):
        from app.config import get_settings  # deferred: cheap + test-friendly

        resolved = limit if limit is not None else int(getattr(get_settings(), setting, 20))
        key = f"rl:{request.url.path}:{_client_key(request, user)}"
        ok_redis = await _allow_redis(key, resolved, window_seconds)
        ok = ok_redis and _allow_memory(f"mem:{key}", resolved, window_seconds)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Slow down and try again in a minute.",
            )
        return True

    return checker
