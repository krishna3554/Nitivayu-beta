"""Test bootstrap: required env defaults before any app import.

The suite runs without live infrastructure (DB-free FakeSession pattern),
but Settings() still requires DATABASE_URL/JWT_SECRET at import time.
Defaults apply only when the environment does not already provide values.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("ALLOW_DEV_OTP", "true")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Keep rate-limit tests hermetic.

    The dev machine may run a real Redis (REDIS_URL in backend/.env), so
    budgets would otherwise leak between tests and between pytest runs.
    Only ephemeral `rl:*`/`mem:` counters are touched — never app data.
    """
    from app.services import rate_limit as rate_limit_mod

    rate_limit_mod._memory_hits.clear()
    try:
        import asyncio as _asyncio

        import redis.asyncio as _redis

        from app.config import get_settings

        url = (get_settings().REDIS_URL or "").strip()
        if url:
            async def _flush():
                client = _redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
                try:
                    keys = await client.keys("rl:*")
                    if keys:
                        await client.delete(*keys)
                finally:
                    await client.aclose()

            _asyncio.run(_flush())
    except Exception:
        pass
    yield
    rate_limit_mod._memory_hits.clear()
