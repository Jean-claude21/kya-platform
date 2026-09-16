"""Transactional storage for the singleton platform-owner claim."""

from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.bootstrap import BootstrapClaim, BootstrapState
from kya_platform.infrastructure.database.models import PlatformBootstrapClaim

_CLAIM_KEY = "platform-owner"


def _domain(row: PlatformBootstrapClaim) -> BootstrapClaim:
    return BootstrapClaim(
        principal_id=row.principal_id,
        owner_fingerprint=row.owner_fingerprint,
        state=cast(BootstrapState, row.state),
    )


class SqlAlchemyBootstrapClaimRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self) -> BootstrapClaim | None:
        async with self._sessions() as session:
            row = await session.get(PlatformBootstrapClaim, _CLAIM_KEY)
            return _domain(row) if row is not None else None

    async def reserve(self, claim: BootstrapClaim) -> BootstrapClaim:
        async with self._sessions.begin() as session:
            await session.execute(
                insert(PlatformBootstrapClaim)
                .values(
                    key=_CLAIM_KEY,
                    principal_id=claim.principal_id,
                    owner_fingerprint=claim.owner_fingerprint,
                    state="reserved",
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
            row = await session.scalar(
                select(PlatformBootstrapClaim).where(PlatformBootstrapClaim.key == _CLAIM_KEY)
            )
            if row is None:
                raise RuntimeError("bootstrap reservation could not be read")
            return _domain(row)

    async def complete(self, principal_id: UUID) -> BootstrapClaim:
        async with self._sessions.begin() as session:
            await session.execute(
                update(PlatformBootstrapClaim)
                .where(
                    PlatformBootstrapClaim.key == _CLAIM_KEY,
                    PlatformBootstrapClaim.principal_id == principal_id,
                )
                .values(state="complete", completed_at=func.now())
            )
            row = await session.get(PlatformBootstrapClaim, _CLAIM_KEY)
            if row is None or row.principal_id != principal_id:
                raise RuntimeError("bootstrap claim ownership changed")
            return _domain(row)


__all__ = ["SqlAlchemyBootstrapClaimRepository"]
