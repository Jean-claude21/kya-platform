"""Use cases and ports for governed data operations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from kya_platform.domain.content import ContentDocument
from kya_platform.domain.data import (
    DataAsset,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataSource,
    IngestionRun,
    QualityResult,
)


class DataConflictError(RuntimeError):
    """A stable identifier or idempotency invariant conflicts."""


class DataReferenceError(RuntimeError):
    """A referenced unit, artifact, source, asset or contract is invalid."""


class DataStateError(RuntimeError):
    """An operation is incompatible with the current lifecycle state."""


@dataclass(frozen=True, slots=True)
class CommandMetadata:
    actor_id: UUID
    correlation_id: UUID
    idempotency_key: str
    request_hash: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not 16 <= len(self.idempotency_key) <= 200:
            raise ValueError("idempotency key must contain 16 to 200 characters")
        if len(self.request_hash) != 64:
            raise ValueError("request hash must be a SHA-256 hexadecimal digest")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("idempotency expiry must include a timezone")


@dataclass(frozen=True, slots=True)
class RunCompletion:
    run: IngestionRun
    snapshot: DataSnapshot
    quality_results: tuple[QualityResult, ...] = ()
    input_snapshot_ids: tuple[UUID, ...] = ()
    content_documents: tuple[ContentDocument, ...] = ()

    def __post_init__(self) -> None:
        if self.run.status.value != "completed":
            raise ValueError("run completion requires a completed run")
        rule_keys = [result.rule_key for result in self.quality_results]
        if len(rule_keys) != len(set(rule_keys)):
            raise ValueError("quality result rule keys must be unique")
        if len(self.input_snapshot_ids) != len(set(self.input_snapshot_ids)):
            raise ValueError("lineage input snapshots must be unique")
        if any(document.snapshot_id != self.snapshot.id for document in self.content_documents):
            raise ValueError("content documents must belong to the completed snapshot")
        document_ordinals = [document.ordinal for document in self.content_documents]
        if document_ordinals != list(range(len(self.content_documents))):
            raise ValueError("content document ordinals must be contiguous")


@dataclass(frozen=True, slots=True)
class SnapshotLineage:
    """Exact snapshot dependencies without exposing storage locations."""

    snapshot_id: UUID
    input_snapshot_ids: tuple[UUID, ...] = ()
    output_snapshot_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class IngestionRunReport:
    """Governed operational view of one ingestion run and its evidence."""

    run: IngestionRun
    pipeline_key: str
    snapshot: DataSnapshot | None = None
    quality_results: tuple[QualityResult, ...] = ()

    def __post_init__(self) -> None:
        if self.snapshot is None and self.quality_results:
            raise ValueError("quality results require a snapshot")
        if self.snapshot is not None and self.snapshot.run_id != self.run.id:
            raise ValueError("snapshot does not belong to the ingestion run")


class DataRepository(Protocol):
    async def list_sources(self, unit_key: str, *, limit: int) -> Sequence[DataSource]: ...
    async def create_source(
        self, unit_key: str, source: DataSource, *, command: CommandMetadata
    ) -> DataSource: ...
    async def list_assets(self, unit_key: str, *, limit: int) -> Sequence[DataAsset]: ...
    async def search_assets(
        self, unit_key: str, query: str, *, limit: int
    ) -> Sequence[DataAsset]: ...
    async def get_asset(self, unit_key: str, asset_key: str) -> DataAsset | None: ...
    async def create_asset(
        self, unit_key: str, asset: DataAsset, *, command: CommandMetadata
    ) -> DataAsset: ...
    async def publish_contract(
        self, unit_key: str, contract: DataContract, *, command: CommandMetadata
    ) -> DataContract: ...
    async def get_contract(
        self, unit_key: str, asset_key: str, *, version: str | None = None
    ) -> DataContract | None: ...
    async def create_pipeline(
        self, unit_key: str, pipeline: DataPipeline, *, command: CommandMetadata
    ) -> DataPipeline: ...
    async def get_pipeline(self, unit_key: str, pipeline_key: str) -> DataPipeline | None: ...
    async def start_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun: ...
    async def get_run(self, unit_key: str, run_id: UUID) -> IngestionRun | None: ...
    async def get_run_report(self, unit_key: str, run_id: UUID) -> IngestionRunReport | None: ...
    async def complete_run(
        self, unit_key: str, completion: RunCompletion, *, command: CommandMetadata
    ) -> RunCompletion: ...
    async def fail_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun: ...
    async def list_snapshots(
        self, unit_key: str, asset_key: str, *, limit: int
    ) -> Sequence[DataSnapshot]: ...
    async def trace_lineage(self, unit_key: str, snapshot_id: UUID) -> SnapshotLineage | None: ...


class DataService:
    """Shared orchestration boundary for HTTP, MCP and connector workers."""

    def __init__(self, repository: DataRepository) -> None:
        self._repository = repository

    async def list_sources(self, unit_key: str, *, limit: int) -> Sequence[DataSource]:
        return await self._repository.list_sources(unit_key, limit=limit)

    async def create_source(
        self, unit_key: str, source: DataSource, *, command: CommandMetadata
    ) -> DataSource:
        return await self._repository.create_source(unit_key, source, command=command)

    async def list_assets(self, unit_key: str, *, limit: int) -> Sequence[DataAsset]:
        return await self._repository.list_assets(unit_key, limit=limit)

    async def search_assets(self, unit_key: str, query: str, *, limit: int) -> Sequence[DataAsset]:
        return await self._repository.search_assets(unit_key, query, limit=limit)

    async def get_asset(self, unit_key: str, asset_key: str) -> DataAsset | None:
        return await self._repository.get_asset(unit_key, asset_key)

    async def create_asset(
        self, unit_key: str, asset: DataAsset, *, command: CommandMetadata
    ) -> DataAsset:
        return await self._repository.create_asset(unit_key, asset, command=command)

    async def publish_contract(
        self, unit_key: str, contract: DataContract, *, command: CommandMetadata
    ) -> DataContract:
        return await self._repository.publish_contract(unit_key, contract, command=command)

    async def get_contract(
        self, unit_key: str, asset_key: str, *, version: str | None = None
    ) -> DataContract | None:
        return await self._repository.get_contract(unit_key, asset_key, version=version)

    async def create_pipeline(
        self, unit_key: str, pipeline: DataPipeline, *, command: CommandMetadata
    ) -> DataPipeline:
        return await self._repository.create_pipeline(unit_key, pipeline, command=command)

    async def get_pipeline(self, unit_key: str, pipeline_key: str) -> DataPipeline | None:
        return await self._repository.get_pipeline(unit_key, pipeline_key)

    async def start_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        return await self._repository.start_run(unit_key, run, command=command)

    async def get_run(self, unit_key: str, run_id: UUID) -> IngestionRun | None:
        return await self._repository.get_run(unit_key, run_id)

    async def get_run_report(self, unit_key: str, run_id: UUID) -> IngestionRunReport | None:
        return await self._repository.get_run_report(unit_key, run_id)

    async def complete_run(
        self, unit_key: str, completion: RunCompletion, *, command: CommandMetadata
    ) -> RunCompletion:
        return await self._repository.complete_run(unit_key, completion, command=command)

    async def fail_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        return await self._repository.fail_run(unit_key, run, command=command)

    async def list_snapshots(
        self, unit_key: str, asset_key: str, *, limit: int
    ) -> Sequence[DataSnapshot]:
        return await self._repository.list_snapshots(unit_key, asset_key, limit=limit)

    async def trace_lineage(self, unit_key: str, snapshot_id: UUID) -> SnapshotLineage | None:
        return await self._repository.trace_lineage(unit_key, snapshot_id)


__all__ = [
    "CommandMetadata",
    "DataConflictError",
    "DataReferenceError",
    "DataRepository",
    "DataService",
    "DataStateError",
    "IngestionRunReport",
    "RunCompletion",
    "SnapshotLineage",
]
