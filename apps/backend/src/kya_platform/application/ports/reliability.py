"""Transaction-bound reliability ports."""

from types import TracebackType
from typing import Protocol, Self

from kya_platform.application.reliability import (
    IdempotencyRequest,
    OutboxMessage,
    StoredCommandResult,
)


class IdempotencyPort(Protocol):
    async def find(self, request: IdempotencyRequest) -> StoredCommandResult | None:
        """Find a previous result inside the active transaction."""

    async def save(self, request: IdempotencyRequest, result: StoredCommandResult) -> None:
        """Persist the deterministic result before the transaction commits."""


class OutboxPort(Protocol):
    async def add(self, message: OutboxMessage) -> None:
        """Persist an external effect in the same transaction as domain changes."""


class UnitOfWork(Protocol):
    idempotency: IdempotencyPort
    outbox: OutboxPort

    async def __aenter__(self) -> Self:
        """Open one transaction."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback automatically unless commit has completed."""

    async def commit(self) -> None:
        """Commit domain changes, outbox events and idempotency result atomically."""


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork:
        """Create an isolated unit of work for one command."""


__all__ = ["IdempotencyPort", "OutboxPort", "UnitOfWork", "UnitOfWorkFactory"]
