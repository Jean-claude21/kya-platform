"""PostgreSQL outbox queue using short transactions and skip-locked leases."""

from datetime import datetime, timedelta
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.infrastructure.database.models.reliability import OutboxEvent
from kya_platform.workers.runner import WorkItem


class LeaseLostError(RuntimeError):
    """The worker no longer owns the item it attempted to finish."""


class _AffectedRows(Protocol):
    rowcount: int


class DatabaseOutboxQueue:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        topics: frozenset[str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._topics = tuple(sorted(topics)) if topics else None

    async def lease(
        self, *, owner: str, limit: int, now: datetime, duration: timedelta
    ) -> list[WorkItem]:
        async with self._session_factory.begin() as session:
            candidate_ids = (
                select(OutboxEvent.id)
                .where(
                    OutboxEvent.processed_at.is_(None),
                    OutboxEvent.dead_lettered_at.is_(None),
                    OutboxEvent.available_at <= now,
                    or_(
                        OutboxEvent.lease_expires_at.is_(None),
                        OutboxEvent.lease_expires_at <= now,
                    ),
                )
                .order_by(OutboxEvent.available_at, OutboxEvent.created_at, OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            if self._topics is not None:
                candidate_ids = candidate_ids.where(OutboxEvent.topic.in_(self._topics))
            ids = list((await session.scalars(candidate_ids)).all())
            if not ids:
                return []

            leased_rows = await session.scalars(
                update(OutboxEvent)
                .where(OutboxEvent.id.in_(ids))
                .values(
                    lease_owner=owner,
                    lease_expires_at=now + duration,
                    attempt_count=OutboxEvent.attempt_count + 1,
                )
                .returning(OutboxEvent)
            )
            return [
                WorkItem(
                    id=row.id,
                    topic=row.topic,
                    payload=dict(row.payload),
                    attempt_count=row.attempt_count,
                )
                for row in leased_rows
            ]

    async def acknowledge(self, item_id: UUID, *, owner: str, processed_at: datetime) -> None:
        await self._finish(
            item_id,
            owner=owner,
            values={
                "processed_at": processed_at,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": None,
            },
        )

    async def retry(
        self, item_id: UUID, *, owner: str, available_at: datetime, error_code: str
    ) -> None:
        await self._finish(
            item_id,
            owner=owner,
            values={
                "available_at": available_at,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": error_code[:256],
            },
        )

    async def dead_letter(
        self, item_id: UUID, *, owner: str, failed_at: datetime, error_code: str
    ) -> None:
        await self._finish(
            item_id,
            owner=owner,
            values={
                "dead_lettered_at": failed_at,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": error_code[:256],
            },
        )

    async def _finish(self, item_id: UUID, *, owner: str, values: dict[str, object]) -> None:
        async with self._session_factory.begin() as session:
            result = cast(
                _AffectedRows,
                await session.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == item_id, OutboxEvent.lease_owner == owner)
                    .values(**values)
                ),
            )
            if result.rowcount != 1:
                raise LeaseLostError("outbox lease is no longer owned")


__all__ = ["DatabaseOutboxQueue", "LeaseLostError"]
