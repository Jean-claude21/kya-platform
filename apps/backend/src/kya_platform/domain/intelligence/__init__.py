"""Governed, deterministic watchlists and citation-ready signals."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WatchStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class SignalStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"


@dataclass(frozen=True, slots=True)
class IntelligenceWatch:
    id: UUID
    key: str
    name: str
    query: str
    owner_unit_id: UUID
    created_by: UUID
    asset_keys: tuple[str, ...] = ()
    status: WatchStatus = WatchStatus.ACTIVE
    revision: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.key or len(self.key) > 120:
            raise ValueError("watch key is required and limited to 120 characters")
        if not self.name.strip() or len(self.name) > 240:
            raise ValueError("watch name is required and limited to 240 characters")
        if not 2 <= len(self.query.strip()) <= 200:
            raise ValueError("watch query must contain between 2 and 200 characters")
        if len(self.asset_keys) > 50 or len(set(self.asset_keys)) != len(self.asset_keys):
            raise ValueError("watch asset keys must be unique and limited to 50")
        if self.revision < 1:
            raise ValueError("watch revision must be positive")


@dataclass(frozen=True, slots=True)
class IntelligenceSignal:
    id: UUID
    watch_id: UUID
    chunk_id: UUID
    snapshot_id: UUID
    citation_id: str
    source_uri: str
    excerpt: str
    observed_at: datetime
    snapshot_digest: str
    page_digest: str
    title: str | None = None
    status: SignalStatus = SignalStatus.OPEN
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.citation_id.startswith("kya:snapshot:"):
            raise ValueError("signal requires a KYA citation")
        if not self.source_uri.startswith("https://"):
            raise ValueError("signal source URI must use HTTPS")
        if not self.excerpt.strip():
            raise ValueError("signal excerpt is required")
        if self.revision < 1:
            raise ValueError("signal revision must be positive")
        acknowledged = self.status is SignalStatus.ACKNOWLEDGED
        if acknowledged != (self.acknowledged_by is not None and self.acknowledged_at is not None):
            raise ValueError("signal acknowledgement fields are inconsistent")


@dataclass(frozen=True, slots=True)
class WatchEvaluation:
    watch: IntelligenceWatch
    created_signals: tuple[IntelligenceSignal, ...]
    matched_count: int


__all__ = [
    "IntelligenceSignal",
    "IntelligenceWatch",
    "SignalStatus",
    "WatchEvaluation",
    "WatchStatus",
]
