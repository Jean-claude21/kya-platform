"""PostgreSQL adapter for governed watchlists and immutable evidence signals."""

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import (
    IntelligenceConflictError,
    IntelligenceReferenceError,
    IntelligenceStateError,
)
from kya_platform.domain.content import ContentSearchHit
from kya_platform.domain.intelligence import (
    IntelligenceSignal,
    IntelligenceWatch,
    SignalStatus,
    WatchStatus,
)
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    CoreOrganizationalUnit,
    IdempotencyRecord,
    IntelligenceSignalRow,
    IntelligenceWatchRow,
    OutboxEvent,
)


def _watch(row: IntelligenceWatchRow) -> IntelligenceWatch:
    return IntelligenceWatch(
        row.id,
        row.key,
        row.name,
        row.query,
        row.owner_unit_id,
        row.created_by,
        tuple(row.asset_keys),
        WatchStatus(row.status),
        row.revision,
        row.created_at,
        row.updated_at,
    )


def _signal(row: IntelligenceSignalRow) -> IntelligenceSignal:
    return IntelligenceSignal(
        row.id,
        row.watch_id,
        row.chunk_id,
        row.snapshot_id,
        row.citation_id,
        row.source_uri,
        row.excerpt,
        row.observed_at,
        row.snapshot_digest,
        row.page_digest,
        row.title,
        SignalStatus(row.status),
        row.acknowledged_by,
        row.acknowledged_at,
        row.revision,
    )


class SqlAlchemyIntelligenceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                scope = f"intelligence:watch:create:{unit_id}:{command.actor_id}"
                replay = await self._replay_ids(session, scope, command)
                if replay:
                    row = await session.get(IntelligenceWatchRow, replay[0])
                    if row is None or row.owner_unit_id != unit_id:
                        raise IntelligenceReferenceError("idempotent watch is unavailable")
                    return _watch(row)
                if watch.owner_unit_id != unit_id:
                    raise IntelligenceReferenceError("watch owner does not match unit")
                row = IntelligenceWatchRow(
                    id=watch.id,
                    key=watch.key,
                    name=watch.name,
                    query=watch.query.strip(),
                    owner_unit_id=unit_id,
                    created_by=command.actor_id,
                    asset_keys=list(watch.asset_keys),
                    status=watch.status.value,
                    revision=1,
                )
                session.add(row)
                session.add_all(
                    [
                        self._event(
                            "kya.intelligence.watch.created.v1", watch.id, unit_id, command
                        ),
                        self._audit(
                            "intelligence.watch.create", "watch", watch.id, unit_id, command
                        ),
                    ]
                )
                self._remember(session, scope, command, (watch.id,))
                await session.flush()
                return _watch(row)
        except IntegrityError as error:
            raise IntelligenceConflictError("watch key already exists in this unit") from error

    async def get_watch(self, unit_key: str, watch_key: str) -> IntelligenceWatch | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            row = await session.scalar(
                select(IntelligenceWatchRow).where(
                    IntelligenceWatchRow.owner_unit_id == unit_id,
                    IntelligenceWatchRow.key == watch_key,
                )
            )
            return _watch(row) if row is not None else None

    async def list_watches(self, unit_key: str, *, limit: int) -> Sequence[IntelligenceWatch]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            rows = tuple(
                await session.scalars(
                    select(IntelligenceWatchRow)
                    .where(IntelligenceWatchRow.owner_unit_id == unit_id)
                    .order_by(IntelligenceWatchRow.updated_at.desc(), IntelligenceWatchRow.id)
                    .limit(limit)
                )
            )
            return tuple(_watch(row) for row in rows)

    async def record_signals(
        self,
        unit_key: str,
        watch: IntelligenceWatch,
        hits: Sequence[ContentSearchHit],
        *,
        command: CommandMetadata,
    ) -> Sequence[IntelligenceSignal]:
        async with self._sessions() as session, session.begin():
            unit_id = await self._required_unit_id(session, unit_key)
            persisted_watch = await session.get(IntelligenceWatchRow, watch.id)
            if persisted_watch is None or persisted_watch.owner_unit_id != unit_id:
                raise IntelligenceReferenceError("watch does not exist in active unit")
            if persisted_watch.status != WatchStatus.ACTIVE.value:
                raise IntelligenceStateError("paused watch cannot be evaluated")
            scope = f"intelligence:watch:evaluate:{watch.id}:{command.actor_id}"
            replay = await self._replay_ids(session, scope, command)
            if replay is not None:
                rows = (
                    tuple(
                        await session.scalars(
                            select(IntelligenceSignalRow).where(
                                IntelligenceSignalRow.id.in_(replay)
                            )
                        )
                    )
                    if replay
                    else ()
                )
                return tuple(_signal(row) for row in rows)

            created: list[IntelligenceSignalRow] = []
            for hit in hits:
                signal_id = uuid7()
                statement = (
                    insert(IntelligenceSignalRow)
                    .values(
                        id=signal_id,
                        watch_id=watch.id,
                        chunk_id=hit.chunk_id,
                        snapshot_id=hit.snapshot_id,
                        citation_id=hit.citation_id,
                        source_uri=hit.source_uri,
                        title=hit.title,
                        excerpt=hit.text,
                        observed_at=hit.observed_at,
                        snapshot_digest=hit.snapshot_digest,
                        page_digest=hit.page_digest,
                        status=SignalStatus.OPEN.value,
                        revision=1,
                    )
                    .on_conflict_do_nothing(index_elements=["watch_id", "chunk_id"])
                    .returning(IntelligenceSignalRow)
                )
                inserted = (await session.execute(statement)).scalar_one_or_none()
                if inserted is not None:
                    created.append(inserted)
            created_ids = tuple(row.id for row in created)
            session.add_all(
                [
                    self._event(
                        "kya.intelligence.watch.evaluated.v1",
                        watch.id,
                        unit_id,
                        command,
                        {"matched_count": len(hits), "created_count": len(created)},
                    ),
                    self._audit(
                        "intelligence.watch.evaluate",
                        "watch",
                        watch.id,
                        unit_id,
                        command,
                        {"matched_count": len(hits), "created_count": len(created)},
                    ),
                ]
            )
            self._remember(session, scope, command, created_ids)
            return tuple(_signal(row) for row in created)

    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool, limit: int
    ) -> Sequence[IntelligenceSignal]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            statement = (
                select(IntelligenceSignalRow)
                .join(
                    IntelligenceWatchRow, IntelligenceWatchRow.id == IntelligenceSignalRow.watch_id
                )
                .where(
                    IntelligenceWatchRow.owner_unit_id == unit_id,
                    IntelligenceWatchRow.key == watch_key,
                )
            )
            if only_open:
                statement = statement.where(IntelligenceSignalRow.status == SignalStatus.OPEN.value)
            rows = tuple(
                await session.scalars(
                    statement.order_by(
                        IntelligenceSignalRow.observed_at.desc(), IntelligenceSignalRow.id
                    ).limit(limit)
                )
            )
            return tuple(_signal(row) for row in rows)

    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal:
        async with self._sessions() as session, session.begin():
            unit_id = await self._required_unit_id(session, unit_key)
            row = await session.scalar(
                select(IntelligenceSignalRow)
                .join(
                    IntelligenceWatchRow, IntelligenceWatchRow.id == IntelligenceSignalRow.watch_id
                )
                .where(
                    IntelligenceSignalRow.id == signal_id,
                    IntelligenceWatchRow.owner_unit_id == unit_id,
                )
                .with_for_update()
            )
            if row is None:
                raise IntelligenceReferenceError("signal does not exist in active unit")
            scope = f"intelligence:signal:acknowledge:{signal_id}:{command.actor_id}"
            replay = await self._replay_ids(session, scope, command)
            if replay is not None:
                return _signal(row)
            if row.revision != expected_revision:
                raise IntelligenceConflictError("signal revision is stale")
            if row.status != SignalStatus.OPEN.value:
                raise IntelligenceStateError("signal is already acknowledged")
            row.status = SignalStatus.ACKNOWLEDGED.value
            row.acknowledged_by = command.actor_id
            row.acknowledged_at = acknowledged_at
            row.revision += 1
            session.add_all(
                [
                    self._event(
                        "kya.intelligence.signal.acknowledged.v1", row.id, unit_id, command
                    ),
                    self._audit(
                        "intelligence.signal.acknowledge", "signal", row.id, unit_id, command
                    ),
                ]
            )
            self._remember(session, scope, command, (row.id,))
            await session.flush()
            return _signal(row)

    @staticmethod
    async def _unit_id(session: AsyncSession, key: str) -> UUID | None:
        return cast(
            UUID | None,
            await session.scalar(
                select(CoreOrganizationalUnit.id).where(CoreOrganizationalUnit.key == key)
            ),
        )

    @classmethod
    async def _required_unit_id(cls, session: AsyncSession, key: str) -> UUID:
        unit_id = await cls._unit_id(session, key)
        if unit_id is None:
            raise IntelligenceReferenceError("organizational unit does not exist")
        return unit_id

    @staticmethod
    async def _replay_ids(
        session: AsyncSession, scope: str, command: CommandMetadata
    ) -> tuple[UUID, ...] | None:
        record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == command.idempotency_key,
            )
        )
        if record is None:
            return None
        if record.request_hash != command.request_hash:
            raise IntelligenceConflictError("idempotency key belongs to another request")
        values = record.response_body.get("ids", [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise IntelligenceConflictError("idempotency evidence is invalid")
        return tuple(UUID(value) for value in values)

    @staticmethod
    def _remember(
        session: AsyncSession,
        scope: str,
        command: CommandMetadata,
        identifiers: tuple[UUID, ...],
    ) -> None:
        session.add(
            IdempotencyRecord(
                scope=scope,
                idempotency_key=command.idempotency_key,
                request_hash=command.request_hash,
                response_status=200,
                response_body={"ids": [str(identifier) for identifier in identifiers]},
                expires_at=command.expires_at,
            )
        )

    @staticmethod
    def _event(
        topic: str,
        aggregate_id: UUID,
        unit_id: UUID,
        command: CommandMetadata,
        extra: dict[str, object] | None = None,
    ) -> OutboxEvent:
        return OutboxEvent(
            topic=topic,
            aggregate_type="intelligence",
            aggregate_id=str(aggregate_id),
            correlation_id=command.correlation_id,
            payload={
                "schema_version": "1",
                "aggregate_id": str(aggregate_id),
                "scope_unit_id": str(unit_id),
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
                **(extra or {}),
            },
        )

    @staticmethod
    def _audit(
        action: str,
        target_type: str,
        target_id: UUID,
        unit_id: UUID,
        command: CommandMetadata,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            actor_id=command.actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            scope=f"org_unit:{unit_id}",
            decision="allowed",
            outcome="succeeded",
            correlation_id=command.correlation_id,
            event_metadata=metadata or {},
        )


__all__ = ["SqlAlchemyIntelligenceRepository"]
