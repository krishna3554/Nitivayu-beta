"""Worker-process database sessions for Temporal activities.

Activities must not reuse FastAPI request-scoped sessions. This module owns a
small process-level async engine/session factory built from the same
``DATABASE_URL`` configuration and models used by the API. Each activity
checks out its own short-lived session via :func:`worker_session`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine = None
_session_factory = None


def _factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    database_url = get_settings().DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _session_factory


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """Yield one short-lived session owned by the calling activity."""
    session = _factory()()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
