"""The source scheduler only materializes due runs through the shared service."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kya_platform.workers import source_scheduler_runtime
from kya_platform.workers.source_scheduler import SourceScheduler

NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scheduler_claims_one_bounded_batch() -> None:
    service = AsyncMock()
    service.claim_due_runs.return_value = (SimpleNamespace(), SimpleNamespace())
    scheduler = SourceScheduler(service, clock=lambda: NOW, batch_size=7)

    assert await scheduler.run_once() == 2
    service.claim_due_runs.assert_awaited_once_with(now=NOW, limit=7)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scheduler_loop_can_stop_without_a_database_specific_hook() -> None:
    service = AsyncMock()
    service.claim_due_runs.return_value = ()
    stop = asyncio.Event()

    async def stop_after_first_sleep(_: float) -> None:
        stop.set()

    await SourceScheduler(service, clock=lambda: NOW).run_forever(
        stop, poll_interval=1, sleep=stop_after_first_sleep
    )

    service.claim_due_runs.assert_awaited_once()


@pytest.mark.unit
def test_scheduler_rejects_unsafe_runtime_bounds() -> None:
    with pytest.raises(ValueError, match="batch size"):
        SourceScheduler(AsyncMock(), batch_size=0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scheduler_runtime_wires_repository_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Engine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    class RuntimeScheduler:
        def __init__(self, service: object) -> None:
            self.service = service

        async def run_forever(self, stop: asyncio.Event) -> None:
            assert not stop.is_set()

    engine = Engine()
    monkeypatch.setattr(
        source_scheduler_runtime,
        "get_settings",
        lambda: SimpleNamespace(database_url="postgresql://db"),
    )
    monkeypatch.setattr(source_scheduler_runtime, "create_engine", lambda value: engine)
    monkeypatch.setattr(
        source_scheduler_runtime, "create_session_factory", lambda value: "sessions"
    )
    monkeypatch.setattr(
        source_scheduler_runtime,
        "SqlAlchemySourceLifecycleRepository",
        lambda value: "repository",
    )
    monkeypatch.setattr(source_scheduler_runtime, "SourceLifecycleService", lambda value: "service")
    monkeypatch.setattr(source_scheduler_runtime, "SourceScheduler", RuntimeScheduler)

    await source_scheduler_runtime.serve()

    assert engine.disposed is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scheduler_runtime_fails_closed_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        source_scheduler_runtime,
        "get_settings",
        lambda: SimpleNamespace(database_url=None),
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        await source_scheduler_runtime.serve()
