import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession


def _database_url() -> str:
    # PgBouncer (transaction pooling) in front of Postgres when configured —
    # the highest-leverage change for concurrent API replicas (§5.6).
    # NOTE: asyncpg + PgBouncer requires prepared-statement care; SQLAlchemy
    # asyncpg disables server-side statement caching issues via pool_pre_ping
    # reconnects, and all queries here are ad-hoc (no named prepared use).
    #
    # Resolve via Settings first so backend/.env is honoured when the process
    # is started plainly (`uvicorn app.main:app`) without exported env vars.
    # Fall back to raw os.environ so import-time never hard-crashes when
    # Settings cannot initialise (e.g. env not yet provided).
    try:
        from app.config import get_settings

        url = get_settings().effective_database_url
        if url:
            return url
    except Exception:
        pass
    return os.getenv("PGBOUNCER_URL") or os.getenv(
        "DATABASE_URL",
        # B4.7 single source of truth: localhost fallback matches backend/.env
        # (compose maps 5433:5432) and Settings.effective_database_url.
        "postgresql+asyncpg://nitivayu_user:nitivayu_secure_password@localhost:5433/nitivayu_db",
    )


DATABASE_URL = ""  # resolved lazily via get_engine(); kept for compat, do not read at import.

_engine = None


def get_engine():
    """Create (once) and return the async engine. A5: no import-time I/O.

    Engine creation is deferred to first use / app lifespan so importing the
    app never crashes when env is missing and tests can set env before first
    DB access. Honors Settings.effective_database_url (PGBOUNCER_URL first).
    """
    global _engine, DATABASE_URL
    if _engine is not None:
        return _engine
    url = _database_url()
    DATABASE_URL = url
    from sqlalchemy.ext.asyncio import create_async_engine as _create

    _engine = _create(
        url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def __getattr__(name: str):
    # Back-compat: `from app.db.session import engine` keeps working but the
    # engine is built lazily on first attribute access, not at import time.
    if name == "engine":
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Create session factory (lazy; use get_session_factory() below).
AsyncSessionLocal = None  # replaced lazily; use get_session_factory() below.


def get_session_factory():
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
