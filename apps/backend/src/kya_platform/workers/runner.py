"""Lease-based worker runner with bounded exponential retry."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

type Payload = Mapping[str, object]
type Handler = Callable[[Payload], Awaitable[None]]
type Clock = Callable[[], datetime]
type Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkItem:
    """One leased event; attempt_count includes the current attempt."""

    id: UUID
    topic: str
    payload: Payload
    attempt_count: int


class WorkQueue(Protocol):
    async def lease(
        self, *, owner: str, limit: int, now: datetime, duration: timedelta
    ) -> list[WorkItem]:
        """Atomically lease available work, reclaiming expired leases."""

    async def acknowledge(self, item_id: UUID, *, owner: str, processed_at: datetime) -> None:
        """Mark a leased item complete if the caller still owns its lease."""

    async def retry(
        self, item_id: UUID, *, owner: str, available_at: datetime, error_code: str
    ) -> None:
        """Release a failed item for a later bounded attempt."""

    async def dead_letter(
        self, item_id: UUID, *, owner: str, failed_at: datetime, error_code: str
    ) -> None:
        """Quarantine exhausted work for explicit operator review."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay: timedelta = timedelta(seconds=5)
    max_delay: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay <= timedelta(0) or self.max_delay < self.base_delay:
            raise ValueError("retry delays must be positive and ordered")

    def delay_for(self, attempt_count: int) -> timedelta:
        exponent = max(0, attempt_count - 1)
        delay_seconds = self.base_delay.total_seconds() * (2**exponent)
        return timedelta(seconds=min(delay_seconds, self.max_delay.total_seconds()))


@dataclass(frozen=True, slots=True)
class RunResult:
    leased: int
    succeeded: int
    retried: int
    dead_lettered: int


class WorkerRunner:
    """Dispatch leased work without holding a database transaction during I/O."""

    def __init__(
        self,
        *,
        queue: WorkQueue,
        handlers: Mapping[str, Handler],
        owner: str,
        retry_policy: RetryPolicy | None = None,
        lease_duration: timedelta = timedelta(minutes=2),
        batch_size: int = 20,
        clock: Clock | None = None,
    ) -> None:
        if not owner.strip():
            raise ValueError("worker owner must be non-empty")
        if batch_size < 1 or lease_duration <= timedelta(0):
            raise ValueError("batch size and lease duration must be positive")
        self._queue = queue
        self._handlers = dict(handlers)
        self._owner = owner
        self._retry_policy = retry_policy or RetryPolicy()
        self._lease_duration = lease_duration
        self._batch_size = batch_size
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_once(self) -> RunResult:
        now = self._clock()
        items = await self._queue.lease(
            owner=self._owner,
            limit=self._batch_size,
            now=now,
            duration=self._lease_duration,
        )
        succeeded = retried = dead_lettered = 0
        for item in items:
            try:
                handler = self._handlers[item.topic]
                await handler(item.payload)
            except (Exception, asyncio.CancelledError) as error:
                if isinstance(error, asyncio.CancelledError):
                    raise
                error_code = type(error).__name__[:256]
                failed_at = self._clock()
                if item.attempt_count >= self._retry_policy.max_attempts:
                    await self._queue.dead_letter(
                        item.id,
                        owner=self._owner,
                        failed_at=failed_at,
                        error_code=error_code,
                    )
                    dead_lettered += 1
                else:
                    await self._queue.retry(
                        item.id,
                        owner=self._owner,
                        available_at=failed_at + self._retry_policy.delay_for(item.attempt_count),
                        error_code=error_code,
                    )
                    retried += 1
            else:
                await self._queue.acknowledge(
                    item.id, owner=self._owner, processed_at=self._clock()
                )
                succeeded += 1
        return RunResult(len(items), succeeded, retried, dead_lettered)

    async def run_forever(
        self,
        stop: asyncio.Event,
        *,
        poll_interval: float = 2.0,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        while not stop.is_set():
            result = await self.run_once()
            if result.leased == 0:
                await sleep(poll_interval)


__all__ = ["Handler", "RetryPolicy", "RunResult", "WorkItem", "WorkQueue", "WorkerRunner"]
