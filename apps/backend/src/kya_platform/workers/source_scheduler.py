"""Small deterministic loop that materializes due ingestion runs."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from kya_platform.application.source_lifecycle import SourceLifecycleService

type Clock = Callable[[], datetime]
type Sleeper = Callable[[float], Awaitable[None]]


class SourceScheduler:
    def __init__(
        self,
        service: SourceLifecycleService,
        *,
        clock: Clock | None = None,
        batch_size: int = 20,
    ) -> None:
        if not 1 <= batch_size <= 100:
            raise ValueError("batch size must be between 1 and 100")
        self._service = service
        self._clock = clock or (lambda: datetime.now(UTC))
        self._batch_size = batch_size

    async def run_once(self) -> int:
        runs = await self._service.claim_due_runs(now=self._clock(), limit=self._batch_size)
        return len(runs)

    async def run_forever(
        self,
        stop: asyncio.Event,
        *,
        poll_interval: float = 15.0,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll interval must be positive")
        while not stop.is_set():
            await self.run_once()
            await sleep(poll_interval)


__all__ = ["SourceScheduler"]
