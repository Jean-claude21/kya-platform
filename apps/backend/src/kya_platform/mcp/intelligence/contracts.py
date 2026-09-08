"""Strict, citation-safe schemas for KYA Intelligence MCP tools."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch
from kya_platform.mcp.registry.contracts import RegistryRisk, RegistryTool


class StrictIntelligenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WatchDetail(StrictIntelligenceContract):
    key: str
    name: str
    query: str
    asset_keys: tuple[str, ...]
    status: str
    revision: int

    @classmethod
    def from_domain(cls, item: IntelligenceWatch) -> WatchDetail:
        return cls(
            key=item.key,
            name=item.name,
            query=item.query,
            asset_keys=item.asset_keys,
            status=item.status.value,
            revision=item.revision,
        )


class SignalDetail(StrictIntelligenceContract):
    signal_id: UUID
    citation_id: str
    source_uri: str
    title: str | None
    excerpt: str
    observed_at: datetime
    snapshot_digest: str
    page_digest: str
    status: str
    revision: int

    @classmethod
    def from_domain(cls, item: IntelligenceSignal) -> SignalDetail:
        return cls(
            signal_id=item.id,
            citation_id=item.citation_id,
            source_uri=item.source_uri,
            title=item.title,
            excerpt=item.excerpt,
            observed_at=item.observed_at,
            snapshot_digest=item.snapshot_digest,
            page_digest=item.page_digest,
            status=item.status.value,
            revision=item.revision,
        )


class WatchListResult(StrictIntelligenceContract):
    items: tuple[WatchDetail, ...]
    active_unit: str
    correlation_id: UUID


class SignalListResult(StrictIntelligenceContract):
    watch_key: str
    items: tuple[SignalDetail, ...]
    active_unit: str
    has_more: bool
    correlation_id: UUID


class WatchEvaluationResult(StrictIntelligenceContract):
    watch: WatchDetail
    matched_count: int
    created_count: int
    created_signals: tuple[SignalDetail, ...]
    active_unit: str
    correlation_id: UUID


class WatchDefinitionInput(StrictIntelligenceContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=120)
    name: str = Field(min_length=1, max_length=240)
    query: str = Field(min_length=2, max_length=200)
    asset_keys: tuple[str, ...] = Field(default=(), max_length=50)


INTELLIGENCE_TOOLS: tuple[RegistryTool, ...] = (
    RegistryTool(
        "list_intelligence_watches", "data:read", "can_view", "org_unit", RegistryRisk.READ
    ),
    RegistryTool(
        "list_intelligence_signals", "data:read", "can_view", "org_unit", RegistryRisk.READ
    ),
    RegistryTool(
        "create_intelligence_watch",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "evaluate_intelligence_watch",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "acknowledge_intelligence_signal",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
)


__all__ = [
    "INTELLIGENCE_TOOLS",
    "SignalDetail",
    "SignalListResult",
    "WatchDefinitionInput",
    "WatchDetail",
    "WatchEvaluationResult",
    "WatchListResult",
]
