"""Tests for lease-based worker execution and bounded retry."""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from kya_platform.workers.runner import RetryPolicy, WorkerRunner, WorkItem


class FakeQueue:
    def __init__(self, items: list[WorkItem]) -> None:
        self.items = items
        self.leases: list[tuple[str, int, datetime, timedelta]] = []
        self.acknowledged: list[UUID] = []
        self.retried: list[tuple[UUID, datetime, str]] = []
        self.dead: list[tuple[UUID, datetime, str]] = []

    async def lease(
        self, *, owner: str, limit: int, now: datetime, duration: timedelta
    ) -> list[WorkItem]:
        self.leases.append((owner, limit, now, duration))
        leased, self.items = self.items[:limit], self.items[limit:]
        return leased

    async def acknowledge(self, item_id: UUID, *, owner: str, processed_at: datetime) -> None:
        self.acknowledged.append(item_id)

    async def retry(
        self, item_id: UUID, *, owner: str, available_at: datetime, error_code: str
    ) -> None:
        self.retried.append((item_id, available_at, error_code))

    async def dead_letter(
        self, item_id: UUID, *, owner: str, failed_at: datetime, error_code: str
    ) -> None:
        self.dead.append((item_id, failed_at, error_code))


NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def item(*, topic: str = "catalog.published", attempt_count: int = 1) -> WorkItem:
    return WorkItem(uuid4(), topic, {"artifact_id": "a-1"}, attempt_count)


@pytest.mark.asyncio
async def test_acknowledges_success_after_handler_completes() -> None:
    work = item()
    queue = FakeQueue([work])
    handled: list[Mapping[str, object]] = []

    async def handle(payload: Mapping[str, object]) -> None:
        handled.append(payload)

    result = await WorkerRunner(
        queue=queue, handlers={work.topic: handle}, owner="worker-a", clock=lambda: NOW
    ).run_once()

    assert result.succeeded == 1
    assert handled == [work.payload]
    assert queue.acknowledged == [work.id]


@pytest.mark.asyncio
async def test_retries_with_exponential_backoff_without_storing_error_message() -> None:
    work = item(attempt_count=3)
    queue = FakeQueue([work])

    async def fail(payload: Mapping[str, object]) -> None:
        raise RuntimeError("do not persist this potentially sensitive value")

    result = await WorkerRunner(
        queue=queue,
        handlers={work.topic: fail},
        owner="worker-a",
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=5)),
        clock=lambda: NOW,
    ).run_once()

    assert result.retried == 1
    assert queue.retried == [(work.id, NOW + timedelta(seconds=20), "RuntimeError")]


@pytest.mark.asyncio
async def test_dead_letters_an_exhausted_item() -> None:
    work = item(attempt_count=5)
    queue = FakeQueue([work])

    async def fail(payload: Mapping[str, object]) -> None:
        raise ValueError("invalid")

    result = await WorkerRunner(
        queue=queue, handlers={work.topic: fail}, owner="worker-a", clock=lambda: NOW
    ).run_once()

    assert result.dead_lettered == 1
    assert queue.dead == [(work.id, NOW, "ValueError")]


@pytest.mark.asyncio
async def test_unknown_topic_is_retried_as_configuration_failure() -> None:
    work = item(topic="unknown")
    queue = FakeQueue([work])

    result = await WorkerRunner(
        queue=queue, handlers={}, owner="worker-a", clock=lambda: NOW
    ).run_once()

    assert result.retried == 1
    assert queue.retried[0][2] == "KeyError"


@pytest.mark.unit
def test_retry_policy_caps_delay_and_rejects_invalid_values() -> None:
    policy = RetryPolicy(base_delay=timedelta(seconds=10), max_delay=timedelta(seconds=25))

    assert policy.delay_for(1) == timedelta(seconds=10)
    assert policy.delay_for(8) == timedelta(seconds=25)
    with pytest.raises(ValueError, match="positive"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="positive and ordered"):
        RetryPolicy(base_delay=timedelta(seconds=30), max_delay=timedelta(seconds=10))


@pytest.mark.unit
def test_runner_rejects_unsafe_runtime_configuration() -> None:
    queue = FakeQueue([])

    with pytest.raises(ValueError, match="owner"):
        WorkerRunner(queue=queue, handlers={}, owner=" ")
    with pytest.raises(ValueError, match="batch size"):
        WorkerRunner(queue=queue, handlers={}, owner="worker-a", batch_size=0)


@pytest.mark.asyncio
async def test_idle_runner_sleeps_until_stop_is_requested() -> None:
    queue = FakeQueue([])
    stop = asyncio.Event()
    sleeps: list[float] = []

    async def stop_after_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        stop.set()

    runner = WorkerRunner(queue=queue, handlers={}, owner="worker-a", clock=lambda: NOW)
    await runner.run_forever(stop, poll_interval=0.25, sleep=stop_after_sleep)

    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_runner_rejects_non_positive_poll_interval() -> None:
    runner = WorkerRunner(queue=FakeQueue([]), handlers={}, owner="worker-a")

    with pytest.raises(ValueError, match="poll_interval"):
        await runner.run_forever(asyncio.Event(), poll_interval=0)
