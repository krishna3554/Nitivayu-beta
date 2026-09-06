import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


def _database_url() -> str:
    # PgBouncer (transaction pooling) in front of Postgres when configured —
    # the highest-leverage change for concurrent API replicas (§5.6).
    # NOTE: asyncpg + PgBouncer requires prepared-statement care; SQLAlchemy
    # asyncpg disables server-side statement caching issues via pool_pre_ping
    # reconnects, and all queries here are ad-hoc (no named prepared use).
    return os.getenv(
        "PGBOUNCER_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://nitivayu_user:nitivayu_secure_password@localhost:5432/nitivayu_db",
        ),
    )


DATABASE_URL = _database_url()

# Create Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
