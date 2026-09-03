"""Application tests for deterministic transaction and outbox semantics."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import uuid7

import pytest

from kya_platform.application import (
    CommandResult,
    IdempotencyConflictError,
    IdempotencyRequest,
    OutboxMessage,
    canonical_request_hash,
    execute_idempotently,
)
from kya_platform.application.reliability import StoredCommandResult


class FakeIdempotency:
    def __init__(self) -> None:
        self.result: StoredCommandResult | None = None
        self.saved = 0

    async def find(self, request: IdempotencyRequest) -> StoredCommandResult | None:
        return self.result

    async def save(self, request: IdempotencyRequest, result: StoredCommandResult) -> None:
        self.result = result
        self.saved += 1


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.idempotency = FakeIdempotency()
        self.outbox = FakeOutbox()
        self.committed = 0
        self.rolled_back = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or self.committed == 0:
            self.rolled_back += 1

    async def commit(self) -> None:
        self.committed += 1


def idempotency_request(payload: dict[str, object]) -> IdempotencyRequest:
    return IdempotencyRequest(
        scope="principal:123:publication",
        key="request-456",
        request_hash=canonical_request_hash(payload),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )


@pytest.mark.unit
def test_request_hash_is_canonical() -> None:
    assert canonical_request_hash({"b": 2, "a": [1, "é"]}) == canonical_request_hash(
        {"a": [1, "é"], "b": 2}
    )


@pytest.mark.unit
async def test_commits_result_and_outbox_atomically() -> None:
    unit_of_work = FakeUnitOfWork()
    request = idempotency_request({"artifact": "skill-1"})

    async def handler(active_unit_of_work: FakeUnitOfWork) -> CommandResult:
        await active_unit_of_work.outbox.add(
            OutboxMessage(
                topic="artifact.published",
                aggregate_type="artifact",
                aggregate_id="skill-1",
                payload={"version": "1.0.0"},
                correlation_id=uuid7(),
            )
        )
        return CommandResult(status_code=201, body={"artifact_id": "skill-1"})

    result = await execute_idempotently(
        request=request,
        unit_of_work_factory=lambda: unit_of_work,
        handler=handler,
    )

    assert result.status_code == 201
    assert unit_of_work.idempotency.saved == 1
    assert len(unit_of_work.outbox.messages) == 1
    assert unit_of_work.committed == 1
    assert unit_of_work.rolled_back == 0


@pytest.mark.unit
async def test_replays_same_result_without_executing_handler() -> None:
    unit_of_work = FakeUnitOfWork()
    request = idempotency_request({"artifact": "skill-1"})
    unit_of_work.idempotency.result = StoredCommandResult(
        request_hash=request.request_hash,
        status_code=201,
        body={"artifact_id": "skill-1"},
    )
    handler_calls = 0

    async def handler(_unit_of_work: FakeUnitOfWork) -> CommandResult:
        nonlocal handler_calls
        handler_calls += 1
        return CommandResult(status_code=500, body={})

    result = await execute_idempotently(
        request=request,
        unit_of_work_factory=lambda: unit_of_work,
        handler=handler,
    )

    assert result == CommandResult(status_code=201, body={"artifact_id": "skill-1"})
    assert handler_calls == 0
    assert unit_of_work.committed == 0
    assert unit_of_work.rolled_back == 1


@pytest.mark.security
async def test_rejects_same_key_with_different_request_hash() -> None:
    unit_of_work = FakeUnitOfWork()
    request = idempotency_request({"artifact": "skill-2"})
    unit_of_work.idempotency.result = StoredCommandResult(
        request_hash=canonical_request_hash({"artifact": "skill-1"}),
        status_code=201,
        body={"artifact_id": "skill-1"},
    )

    async def handler(_unit_of_work: FakeUnitOfWork) -> CommandResult:
        return CommandResult(status_code=201, body={})

    with pytest.raises(IdempotencyConflictError):
        await execute_idempotently(
            request=request,
            unit_of_work_factory=lambda: unit_of_work,
            handler=handler,
        )

    assert unit_of_work.committed == 0
    assert unit_of_work.rolled_back == 1


@pytest.mark.unit
async def test_handler_failure_rolls_back_without_storing_result() -> None:
    unit_of_work = FakeUnitOfWork()
    request = idempotency_request({"artifact": "skill-1"})

    async def handler(_unit_of_work: FakeUnitOfWork) -> CommandResult:
        raise RuntimeError("deterministic failure")

    with pytest.raises(RuntimeError):
        await execute_idempotently(
            request=request,
            unit_of_work_factory=lambda: unit_of_work,
            handler=handler,
        )

    assert unit_of_work.idempotency.saved == 0
    assert unit_of_work.committed == 0
    assert unit_of_work.rolled_back == 1


@pytest.mark.parametrize(
    ("scope", "key", "request_hash"),
    [("", "key", "0" * 64), ("scope", "", "0" * 64), ("scope", "key", "short")],
)
def test_rejects_invalid_idempotency_metadata(scope: str, key: str, request_hash: str) -> None:
    with pytest.raises(ValueError):
        IdempotencyRequest(
            scope=scope,
            key=key,
            request_hash=request_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
