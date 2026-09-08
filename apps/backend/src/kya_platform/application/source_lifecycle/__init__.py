"""Use cases for atomically configuring and operating source flows."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from kya_platform.application.data import CommandMetadata
from kya_platform.domain.data import DataStatus, IngestionRun
from kya_platform.domain.source_lifecycle import (
    IngestionSchedule,
    SourceFlow,
    SourceFlowDraft,
    SourceFlowHealth,
)


class SourceFlowConflictError(RuntimeError):
    """A stable key, idempotency invariant or optimistic revision conflicts."""


class SourceFlowReferenceError(RuntimeError):
    """A unit or published connector reference is invalid."""


class SourceFlowStateError(RuntimeError):
    """A requested source-flow transition is invalid."""


class SourceLifecycleRepository(Protocol):
    async def configure(
        self,
        unit_key: str,
        draft: SourceFlowDraft,
        *,
        schedule: IngestionSchedule | None,
        command: CommandMetadata,
    ) -> SourceFlow: ...

    async def get(self, unit_key: str, flow_key: str) -> SourceFlow | None: ...
    async def get_health(self, unit_key: str, flow_key: str) -> SourceFlowHealth | None: ...

    async def transition(
        self,
        unit_key: str,
        flow_key: str,
        status: DataStatus,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow: ...

    async def put_schedule(
        self,
        unit_key: str,
        flow_key: str,
        schedule: IngestionSchedule,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow: ...

    async def claim_due_runs(self, *, now: datetime, limit: int) -> Sequence[IngestionRun]: ...


class SourceLifecycleService:
    def __init__(self, repository: SourceLifecycleRepository) -> None:
        self._repository = repository

    async def configure(
        self,
        unit_key: str,
        draft: SourceFlowDraft,
        *,
        schedule: IngestionSchedule | None,
        command: CommandMetadata,
    ) -> SourceFlow:
        return await self._repository.configure(unit_key, draft, schedule=schedule, command=command)

    async def get_health(self, unit_key: str, flow_key: str) -> SourceFlowHealth | None:
        return await self._repository.get_health(unit_key, flow_key)

    async def transition(
        self,
        unit_key: str,
        flow_key: str,
        status: DataStatus,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        if status not in {DataStatus.ACTIVE, DataStatus.PAUSED}:
            raise SourceFlowStateError("only active and paused transitions are supported")
        return await self._repository.transition(
            unit_key,
            flow_key,
            status,
            expected_revision=expected_revision,
            command=command,
        )

    async def put_schedule(
        self,
        unit_key: str,
        flow_key: str,
        schedule: IngestionSchedule,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        return await self._repository.put_schedule(
            unit_key,
            flow_key,
            schedule,
            expected_revision=expected_revision,
            command=command,
        )

    async def claim_due_runs(self, *, now: datetime, limit: int = 20) -> Sequence[IngestionRun]:
        if not 1 <= limit <= 100:
            raise ValueError("claim limit must be between 1 and 100")
        return await self._repository.claim_due_runs(now=now, limit=limit)


__all__ = [
    "SourceFlowConflictError",
    "SourceFlowReferenceError",
    "SourceFlowStateError",
    "SourceLifecycleRepository",
    "SourceLifecycleService",
]
