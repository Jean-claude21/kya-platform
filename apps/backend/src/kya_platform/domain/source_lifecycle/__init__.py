"""Aggregate primitives for autonomous governed source flows."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from kya_platform.domain.data import (
    DataAsset,
    DataContract,
    DataPipeline,
    DataSource,
    DataStatus,
    IngestionRun,
)


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


@dataclass(frozen=True, slots=True)
class SourceFlowDraft:
    source: DataSource
    asset: DataAsset
    contract: DataContract
    pipeline: DataPipeline
    connector_key: str
    connector_version: str

    def __post_init__(self) -> None:
        if not self.connector_key.strip() or not self.connector_version.strip():
            raise ValueError("connector key and version are required")
        owner_ids = {
            self.source.owner_unit_id,
            self.asset.owner_unit_id,
            self.pipeline.owner_unit_id,
        }
        if len(owner_ids) != 1:
            raise ValueError("source flow components must share one owner")
        if self.contract.asset_id != self.asset.id:
            raise ValueError("source flow contract must belong to its asset")
        if self.pipeline.source_id != self.source.id:
            raise ValueError("source flow pipeline must use its source")
        if self.pipeline.output_asset_id != self.asset.id:
            raise ValueError("source flow pipeline must produce its asset")


@dataclass(frozen=True, slots=True)
class IngestionSchedule:
    id: UUID
    pipeline_id: UUID
    interval_minutes: int
    next_run_at: datetime
    enabled: bool = True
    revision: int = 1
    last_claimed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 15 <= self.interval_minutes <= 43_200:
            raise ValueError("schedule interval must be between 15 and 43200 minutes")
        _aware(self.next_run_at, "next_run_at")
        if self.last_claimed_at is not None:
            _aware(self.last_claimed_at, "last_claimed_at")
        if self.revision < 1:
            raise ValueError("schedule revision must be positive")


@dataclass(frozen=True, slots=True)
class SourceFlow:
    key: str
    source: DataSource
    asset: DataAsset
    contract: DataContract
    pipeline: DataPipeline
    revision: int
    schedule: IngestionSchedule | None = None

    def __post_init__(self) -> None:
        if self.key != self.pipeline.key:
            raise ValueError("source flow key must match its pipeline key")
        if self.revision < 1:
            raise ValueError("source flow revision must be positive")

    @property
    def status(self) -> DataStatus:
        statuses = {self.source.status, self.asset.status, self.pipeline.status}
        if len(statuses) != 1:
            raise ValueError("source flow component states have diverged")
        return next(iter(statuses))


@dataclass(frozen=True, slots=True)
class SourceFlowHealth:
    flow: SourceFlow
    latest_run: IngestionRun | None = None
    latest_snapshot_id: UUID | None = None
    latest_snapshot_observed_at: datetime | None = None
    quality_status: str | None = None


__all__ = [
    "IngestionSchedule",
    "SourceFlow",
    "SourceFlowDraft",
    "SourceFlowHealth",
]
