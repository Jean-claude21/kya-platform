"""SQLAlchemy identity mapping that fails closed for deprovisioned principals."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.infrastructure.database.models import ExternalIdentity


class SqlAlchemyIdentityMapping:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        async with self._session_factory() as session:
            statement = select(ExternalIdentity.principal_id).where(
                ExternalIdentity.issuer == identity.issuer,
                ExternalIdentity.subject == identity.subject,
                ExternalIdentity.disabled_at.is_(None),
            )
            return cast(UUID | None, await session.scalar(statement))

    async def disable_principal(self, principal_id: UUID, *, disabled_at: datetime) -> int:
        async with self._session_factory.begin() as session:
            result = await session.execute(
                update(ExternalIdentity)
                .where(
                    ExternalIdentity.principal_id == principal_id,
                    ExternalIdentity.disabled_at.is_(None),
                )
                .values(disabled_at=disabled_at)
            )
            return result.rowcount  # type: ignore[attr-defined, no-any-return]


__all__ = ["SqlAlchemyIdentityMapping"]
