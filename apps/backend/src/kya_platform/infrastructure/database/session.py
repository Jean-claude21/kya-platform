"""Async database resources without global mutable sessions."""

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: SecretStr) -> AsyncEngine:
    """Create a bounded, liveness-checked runtime engine."""

    return create_async_engine(
        database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create request-scoped sessions; one session must serve one task."""

    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


__all__ = ["create_engine", "create_session_factory"]
