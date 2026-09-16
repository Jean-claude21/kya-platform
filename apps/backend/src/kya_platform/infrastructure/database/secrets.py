"""Neon adapter for secret reference governance; values never enter this module."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.infrastructure.database.models import SecretReferenceRow
from kya_platform.secrets import SecretKind, SecretReference, SecretStatus


def _reference(row: SecretReferenceRow) -> SecretReference:
    return SecretReference(
        id=row.id,
        kind=SecretKind(row.kind),
        provider=row.provider,
        locator=row.locator,
        key_name=row.key_name,
        owner_scope=row.owner_scope,
        purpose=row.purpose,
        environment=row.environment,
        status=SecretStatus(row.status),
        created_at=row.created_at,
        rotated_at=row.rotated_at,
        expires_at=row.expires_at,
    )


class SqlAlchemySecretReferenceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, reference_id: UUID) -> SecretReference | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(SecretReferenceRow).where(SecretReferenceRow.id == reference_id)
            )
            return _reference(row) if row is not None else None

    async def list_for_scope(self, owner_scope: str) -> Sequence[SecretReference]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(SecretReferenceRow).where(SecretReferenceRow.owner_scope == owner_scope)
            )
            return tuple(_reference(row) for row in rows)

    async def list_by_ids(self, reference_ids: tuple[UUID, ...]) -> Sequence[SecretReference]:
        if not reference_ids:
            return ()
        async with self._sessions() as session:
            rows = await session.scalars(
                select(SecretReferenceRow).where(SecretReferenceRow.id.in_(reference_ids))
            )
            by_id = {row.id: row for row in rows}
            return tuple(
                _reference(by_id[reference_id])
                for reference_id in reference_ids
                if reference_id in by_id
            )

    async def register(self, reference: SecretReference) -> None:
        async with self._sessions() as session:
            existing = await session.get(SecretReferenceRow, reference.id)
            if existing is None:
                session.add(
                    SecretReferenceRow(
                        id=reference.id,
                        kind=reference.kind.value,
                        provider=reference.provider,
                        locator=reference.locator,
                        key_name=reference.key_name,
                        owner_scope=reference.owner_scope,
                        purpose=reference.purpose,
                        environment=reference.environment,
                        status=reference.status.value,
                        expires_at=reference.expires_at,
                    )
                )
            else:
                existing.kind = reference.kind.value
                existing.provider = reference.provider
                existing.locator = reference.locator
                existing.key_name = reference.key_name
                existing.owner_scope = reference.owner_scope
                existing.purpose = reference.purpose
                existing.environment = reference.environment
                existing.status = reference.status.value
                existing.expires_at = reference.expires_at
            await session.commit()

    async def revoke(self, reference_id: UUID) -> None:
        async with self._sessions() as session:
            row = await session.get(SecretReferenceRow, reference_id)
            if row is None:
                return
            row.status = SecretStatus.REVOKED.value
            await session.commit()


__all__ = ["SqlAlchemySecretReferenceRepository"]
