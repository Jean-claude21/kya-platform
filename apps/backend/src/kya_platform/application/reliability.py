"""Deterministic command execution with replay and transactional outbox."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from kya_platform.application.ports.reliability import UnitOfWork, UnitOfWorkFactory

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | Mapping[str, JsonValue] | Sequence[JsonValue]


@dataclass(frozen=True, slots=True)
class IdempotencyRequest:
    """Caller-scoped key and hash identifying one logical command."""

    scope: str
    key: str
    request_hash: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.scope or len(self.scope) > 255:
            raise ValueError("idempotency scope must contain 1 to 255 characters")
        if not self.key or len(self.key) > 255:
            raise ValueError("idempotency key must contain 1 to 255 characters")
        if len(self.request_hash) != 64:
            raise ValueError("request_hash must be a SHA-256 hexadecimal digest")


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Public deterministic result of a command."""

    status_code: int
    body: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class StoredCommandResult:
    """Result plus request hash retained for safe replay detection."""

    request_hash: str
    status_code: int
    body: Mapping[str, JsonValue]

    def as_command_result(self) -> CommandResult:
        return CommandResult(status_code=self.status_code, body=self.body)


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """External effect to dispatch only after its transaction commits."""

    topic: str
    aggregate_type: str
    aggregate_id: str
    payload: Mapping[str, JsonValue]
    correlation_id: UUID

    def __post_init__(self) -> None:
        if not self.topic or not self.aggregate_type or not self.aggregate_id:
            raise ValueError("outbox routing fields must be non-empty")


class IdempotencyConflictError(ValueError):
    """The caller reused a key for a semantically different command."""


def canonical_request_hash(payload: JsonValue) -> str:
    """Hash a JSON value independently of object key order or whitespace."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


async def execute_idempotently(
    *,
    request: IdempotencyRequest,
    unit_of_work_factory: UnitOfWorkFactory,
    handler: Callable[[UnitOfWork], Awaitable[CommandResult]],
) -> CommandResult:
    """Execute once; callers must express external effects through the outbox."""

    async with unit_of_work_factory() as unit_of_work:
        previous = await unit_of_work.idempotency.find(request)
        if previous is not None:
            if previous.request_hash != request.request_hash:
                raise IdempotencyConflictError("idempotency key already belongs to another request")
            return previous.as_command_result()

        result = await handler(unit_of_work)
        stored = StoredCommandResult(
            request_hash=request.request_hash,
            status_code=result.status_code,
            body=dict(result.body),
        )
        await unit_of_work.idempotency.save(request, stored)
        await unit_of_work.commit()
        return result


__all__ = [
    "CommandResult",
    "IdempotencyConflictError",
    "IdempotencyRequest",
    "JsonValue",
    "OutboxMessage",
    "StoredCommandResult",
    "canonical_request_hash",
    "execute_idempotently",
]
