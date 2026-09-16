"""Append-only, secret-safe audit recording and scoped read models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Protocol
from uuid import UUID

type AuditScalar = str | int | float | bool | None
type AuditValue = AuditScalar | Mapping[str, AuditValue] | tuple[AuditValue, ...]

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "password",
    "private_key",
    "secret",
    "token",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _freeze_and_redact(value: object, *, key: str | None = None) -> AuditValue:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        sanitized = {
            str(item_key): _freeze_and_redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
        return MappingProxyType(sanitized)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_and_redact(item) for item in value)
    return str(value)


def _safe_mapping(value: Mapping[str, object] | None) -> Mapping[str, AuditValue]:
    frozen = _freeze_and_redact(value or {})
    if not isinstance(frozen, Mapping):
        raise TypeError("audit metadata must be a mapping")
    return frozen


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Immutable evidence describing one request, decision or sensitive execution."""

    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    actor_context: Mapping[str, AuditValue]
    action: str
    target_type: str
    target_id: str
    scope: str
    environment: str | None
    decision: str | None
    outcome: str
    correlation_id: UUID
    metadata: Mapping[str, AuditValue]
    causation_id: UUID | None = None
    protected_content: Mapping[str, AuditValue] | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        for field_name in ("action", "target_type", "target_id", "scope", "outcome"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        object.__setattr__(self, "actor_context", _safe_mapping(self.actor_context))
        object.__setattr__(self, "metadata", _safe_mapping(self.metadata))
        if self.protected_content is not None:
            object.__setattr__(
                self,
                "protected_content",
                _safe_mapping(self.protected_content),
            )

    def with_metadata(self, metadata: Mapping[str, object]) -> AuditEvent:
        """Return a new event; the original record is never mutated."""

        return replace(self, metadata=_safe_mapping(metadata))


@dataclass(frozen=True, slots=True)
class AuditQuery:
    """Bounded query for exactly one authorized workspace."""

    scope: str
    target_type: str | None = None
    target_id: str | None = None
    correlation_id: UUID | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        prefix, separator, workspace_key = self.scope.partition(":")
        if prefix != "workspace" or separator != ":" or not workspace_key:
            raise ValueError("audit queries must target exactly one workspace scope")
        if not 1 <= self.limit <= 200:
            raise ValueError("audit query limit must be between 1 and 200")


class AuditRepository(Protocol):
    """Storage contract deliberately exposes append and scoped reads only."""

    async def append(self, event: AuditEvent) -> None:
        """Persist one new immutable event."""

    async def list_events(self, query: AuditQuery) -> Sequence[AuditEvent]:
        """Return only events matching the already-authorized scope."""


class InMemoryAuditRepository:
    """Deterministic repository for tests and isolated demonstrations."""

    def __init__(self) -> None:
        self._events: dict[UUID, AuditEvent] = {}

    async def append(self, event: AuditEvent) -> None:
        if event.id in self._events:
            raise ValueError("audit event identifiers are immutable and unique")
        self._events[event.id] = event

    async def list_events(self, query: AuditQuery) -> tuple[AuditEvent, ...]:
        matches = (
            event
            for event in self._events.values()
            if event.scope == query.scope
            and (query.target_type is None or event.target_type == query.target_type)
            and (query.target_id is None or event.target_id == query.target_id)
            and (query.correlation_id is None or event.correlation_id == query.correlation_id)
        )
        return tuple(
            sorted(matches, key=lambda item: (item.occurred_at, str(item.id)), reverse=True)[
                : query.limit
            ]
        )


@dataclass(frozen=True, slots=True)
class AuditEventView:
    """An audit event whose protected content follows a separate authorization decision."""

    event: AuditEvent
    protected_content: Mapping[str, AuditValue] | None


class AuditWriter:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def append(self, event: AuditEvent) -> AuditEvent:
        """Sanitize at the application boundary before storage."""

        safe_event = replace(
            event,
            actor_context=_safe_mapping(event.actor_context),
            metadata=_safe_mapping(event.metadata),
            protected_content=(
                _safe_mapping(event.protected_content)
                if event.protected_content is not None
                else None
            ),
        )
        await self._repository.append(safe_event)
        return safe_event


class AuditQueryService:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def list_events(
        self,
        query: AuditQuery,
        *,
        may_view_protected_content: bool,
    ) -> tuple[AuditEventView, ...]:
        events = await self._repository.list_events(query)
        return tuple(
            AuditEventView(
                event=event,
                protected_content=(event.protected_content if may_view_protected_content else None),
            )
            for event in events
        )


__all__ = [
    "AuditEvent",
    "AuditEventView",
    "AuditQuery",
    "AuditQueryService",
    "AuditRepository",
    "AuditValue",
    "AuditWriter",
    "InMemoryAuditRepository",
]
