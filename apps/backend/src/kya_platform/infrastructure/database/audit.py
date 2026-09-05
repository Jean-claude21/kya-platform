"""SQLAlchemy adapter for append-only audit evidence in Neon Postgres."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.audit import AuditEvent as DomainAuditEvent
from kya_platform.application.audit import AuditQuery, AuditValue
from kya_platform.infrastructure.database.models import AuditEvent as AuditEventRow

_ACTOR_CONTEXT = "_actor_context"
_PROTECTED_CONTENT = "_protected_content"


def _to_json(value: AuditValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _to_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    return value


def _event_from_row(row: AuditEventRow) -> DomainAuditEvent:
    stored_metadata = dict(row.event_metadata)
    actor_context = stored_metadata.pop(_ACTOR_CONTEXT, {})
    protected_content = stored_metadata.pop(_PROTECTED_CONTENT, None)
    return DomainAuditEvent(
        id=row.id,
        occurred_at=row.occurred_at,
        actor_id=row.actor_id,
        actor_context=actor_context,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        scope=row.scope or "workspace:unknown",
        environment=row.environment,
        decision=row.decision,
        outcome=row.outcome,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        metadata=stored_metadata,
        protected_content=protected_content,
    )


class SqlAlchemyAuditRepository:
    """Persist through INSERT and expose no mutation method by construction."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def append(self, event: DomainAuditEvent) -> None:
        metadata = {key: _to_json(value) for key, value in event.metadata.items()}
        metadata[_ACTOR_CONTEXT] = _to_json(event.actor_context)
        if event.protected_content is not None:
            metadata[_PROTECTED_CONTENT] = _to_json(event.protected_content)
        async with self._sessions() as session:
            session.add(
                AuditEventRow(
                    id=event.id,
                    occurred_at=event.occurred_at,
                    actor_id=event.actor_id,
                    action=event.action,
                    target_type=event.target_type,
                    target_id=event.target_id,
                    scope=event.scope,
                    environment=event.environment,
                    decision=event.decision,
                    outcome=event.outcome,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    event_metadata=metadata,
                )
            )
            await session.commit()

    async def list_events(self, query: AuditQuery) -> Sequence[DomainAuditEvent]:
        statement: Select[tuple[AuditEventRow]] = select(AuditEventRow).where(
            AuditEventRow.scope == query.scope
        )
        if query.target_type is not None:
            statement = statement.where(AuditEventRow.target_type == query.target_type)
        if query.target_id is not None:
            statement = statement.where(AuditEventRow.target_id == query.target_id)
        if query.correlation_id is not None:
            statement = statement.where(AuditEventRow.correlation_id == query.correlation_id)
        statement = statement.order_by(
            AuditEventRow.occurred_at.desc(), AuditEventRow.id.desc()
        ).limit(query.limit)
        async with self._sessions() as session:
            result = await session.execute(statement)
            return tuple(_event_from_row(row) for row in result.scalars().all())


__all__ = ["SqlAlchemyAuditRepository"]
