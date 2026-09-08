"""Use cases for deterministic, governed intelligence watchlists."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from kya_platform.application.content import ContentService
from kya_platform.application.data import CommandMetadata
from kya_platform.domain.content import ContentSearchHit
from kya_platform.domain.intelligence import (
    IntelligenceSignal,
    IntelligenceWatch,
    WatchEvaluation,
)


class IntelligenceConflictError(RuntimeError):
    """An idempotency key, stable key or optimistic revision conflicts."""


class IntelligenceReferenceError(RuntimeError):
    """A requested watch, signal or organizational unit does not exist."""


class IntelligenceStateError(RuntimeError):
    """The requested operation is incompatible with current state."""


class IntelligenceRepository(Protocol):
    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch: ...

    async def get_watch(self, unit_key: str, watch_key: str) -> IntelligenceWatch | None: ...

    async def list_watches(self, unit_key: str, *, limit: int) -> Sequence[IntelligenceWatch]: ...

    async def record_signals(
        self,
        unit_key: str,
        watch: IntelligenceWatch,
        hits: Sequence[ContentSearchHit],
        *,
        command: CommandMetadata,
    ) -> Sequence[IntelligenceSignal]: ...

    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool, limit: int
    ) -> Sequence[IntelligenceSignal]: ...

    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal: ...


class IntelligenceService:
    def __init__(self, repository: IntelligenceRepository, content: ContentService) -> None:
        self._repository = repository
        self._content = content

    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch:
        return await self._repository.create_watch(unit_key, watch, command=command)

    async def list_watches(self, unit_key: str, *, limit: int = 20) -> Sequence[IntelligenceWatch]:
        if not 1 <= limit <= 100:
            raise ValueError("watch limit must be between 1 and 100")
        return await self._repository.list_watches(unit_key, limit=limit)

    async def evaluate_watch(
        self,
        unit_key: str,
        watch_key: str,
        *,
        limit: int,
        command: CommandMetadata,
    ) -> WatchEvaluation:
        if not 1 <= limit <= 50:
            raise ValueError("evaluation limit must be between 1 and 50")
        watch = await self._repository.get_watch(unit_key, watch_key)
        if watch is None:
            raise IntelligenceReferenceError("watch does not exist")
        if watch.status.value != "active":
            raise IntelligenceStateError("paused watch cannot be evaluated")
        hits = await self._content.search_public_content(
            unit_key, watch.query, asset_keys=watch.asset_keys, limit=limit
        )
        created = await self._repository.record_signals(unit_key, watch, hits, command=command)
        return WatchEvaluation(watch, tuple(created), len(hits))

    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool = True, limit: int = 20
    ) -> Sequence[IntelligenceSignal]:
        if not 1 <= limit <= 100:
            raise ValueError("signal limit must be between 1 and 100")
        return await self._repository.list_signals(
            unit_key, watch_key, only_open=only_open, limit=limit
        )

    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal:
        return await self._repository.acknowledge_signal(
            unit_key,
            signal_id,
            expected_revision=expected_revision,
            acknowledged_at=acknowledged_at,
            command=command,
        )


__all__ = [
    "IntelligenceConflictError",
    "IntelligenceReferenceError",
    "IntelligenceRepository",
    "IntelligenceService",
    "IntelligenceStateError",
]
