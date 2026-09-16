"""Strict, secret-safe schemas for governed Data MCP tools."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kya_platform.domain.content import ContentSearchHit
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataSnapshot,
    DataSourceKind,
    DataStatus,
    QualityResult,
)
from kya_platform.domain.source_lifecycle import SourceFlow, SourceFlowHealth
from kya_platform.mcp.registry.contracts import RegistryRisk, RegistryTool


class StrictDataMcpContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataAssetSummary(StrictDataMcpContract):
    key: str
    name: str
    layer: DataAssetLayer
    classification: DataClassification
    status: DataStatus

    @classmethod
    def from_domain(cls, asset: DataAsset) -> DataAssetSummary:
        return cls(
            key=asset.key,
            name=asset.name,
            layer=asset.layer,
            classification=asset.classification,
            status=asset.status,
        )


class DataDiscoveryResult(StrictDataMcpContract):
    items: tuple[DataAssetSummary, ...]
    active_unit: str
    has_more: bool
    correlation_id: UUID


class DataAssetDetail(DataAssetSummary):
    asset_id: UUID
    active_unit: str
    correlation_id: UUID

    @classmethod
    def from_detail(
        cls, asset: DataAsset, *, active_unit: str, correlation_id: UUID
    ) -> DataAssetDetail:
        return cls(
            asset_id=asset.id,
            key=asset.key,
            name=asset.name,
            layer=asset.layer,
            classification=asset.classification,
            status=asset.status,
            active_unit=active_unit,
            correlation_id=correlation_id,
        )


class QualityRuleDetail(StrictDataMcpContract):
    key: str
    kind: str
    expression: str
    severity: str


class DataContractDetail(StrictDataMcpContract):
    contract_id: UUID
    asset_key: str
    version: str
    schema_document: dict[str, object]
    digest: str
    quality_rules: tuple[QualityRuleDetail, ...]
    freshness_minutes: int | None
    retention_days: int | None
    active_unit: str
    correlation_id: UUID

    @classmethod
    def from_domain(
        cls,
        contract: DataContract,
        *,
        asset_key: str,
        active_unit: str,
        correlation_id: UUID,
    ) -> DataContractDetail:
        return cls(
            contract_id=contract.id,
            asset_key=asset_key,
            version=contract.version,
            schema_document=contract.schema,
            digest=contract.digest,
            quality_rules=tuple(
                QualityRuleDetail(
                    key=rule.key,
                    kind=rule.kind,
                    expression=rule.expression,
                    severity=rule.severity,
                )
                for rule in contract.quality_rules
            ),
            freshness_minutes=contract.freshness_minutes,
            retention_days=contract.retention_days,
            active_unit=active_unit,
            correlation_id=correlation_id,
        )


class SnapshotSummary(StrictDataMcpContract):
    snapshot_id: UUID
    contract_id: UUID
    content_digest: str
    media_type: str
    observed_at: datetime
    row_count: int | None
    byte_size: int | None

    @classmethod
    def from_domain(cls, snapshot: DataSnapshot) -> SnapshotSummary:
        return cls(
            snapshot_id=snapshot.id,
            contract_id=snapshot.contract_id,
            content_digest=snapshot.content_digest,
            media_type=snapshot.media_type,
            observed_at=snapshot.observed_at,
            row_count=snapshot.row_count,
            byte_size=snapshot.byte_size,
        )


class SnapshotListResult(StrictDataMcpContract):
    asset_key: str
    items: tuple[SnapshotSummary, ...]
    active_unit: str
    has_more: bool
    correlation_id: UUID


class LineageResult(StrictDataMcpContract):
    snapshot_id: UUID
    input_snapshot_ids: tuple[UUID, ...]
    output_snapshot_ids: tuple[UUID, ...]
    active_unit: str
    correlation_id: UUID


class IngestionAccepted(StrictDataMcpContract):
    run_id: UUID
    pipeline_key: str
    status: str
    started_at: datetime
    active_unit: str
    correlation_id: UUID


class QualityResultDetail(StrictDataMcpContract):
    rule_key: str
    status: str
    observed: dict[str, object] | None

    @classmethod
    def from_domain(cls, result: QualityResult) -> QualityResultDetail:
        return cls(
            rule_key=result.rule_key,
            status=result.status.value,
            observed=result.observed,
        )


class IngestionRunDetail(StrictDataMcpContract):
    run_id: UUID
    pipeline_key: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None
    snapshot: SnapshotSummary | None
    quality_results: tuple[QualityResultDetail, ...]
    active_unit: str
    correlation_id: UUID


class ContentCitation(StrictDataMcpContract):
    citation_id: str
    snapshot_id: UUID
    snapshot_digest: str
    page_digest: str
    source_uri: str
    observed_at: datetime
    char_start: int
    char_end: int


class ContentHitDetail(StrictDataMcpContract):
    chunk_id: UUID
    asset_key: str
    title: str | None
    text: str
    score: float
    search_mode: str
    content_trust: str
    citation: ContentCitation

    @classmethod
    def from_domain(cls, hit: ContentSearchHit) -> ContentHitDetail:
        return cls(
            chunk_id=hit.chunk_id,
            asset_key=hit.asset_key,
            title=hit.title,
            text=hit.text,
            score=hit.score,
            search_mode="lexical",
            content_trust=hit.content_trust,
            citation=ContentCitation(
                citation_id=hit.citation_id,
                snapshot_id=hit.snapshot_id,
                snapshot_digest=hit.snapshot_digest,
                page_digest=hit.page_digest,
                source_uri=hit.source_uri,
                observed_at=hit.observed_at,
                char_start=hit.char_start,
                char_end=hit.char_end,
            ),
        )


class ContentSearchResult(StrictDataMcpContract):
    items: tuple[ContentHitDetail, ...]
    active_unit: str
    search_mode: str
    has_more: bool
    correlation_id: UUID


class ContentExcerptResult(StrictDataMcpContract):
    item: ContentHitDetail
    active_unit: str
    correlation_id: UUID


class SourceConnectorInput(StrictDataMcpContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=120)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class SourceScheduleInput(StrictDataMcpContract):
    interval_minutes: int = Field(ge=15, le=43_200)
    next_run_at: datetime
    enabled: bool = True

    @field_validator("next_run_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("next_run_at must include a timezone")
        return value


class SourceQualityRuleInput(StrictDataMcpContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=120)
    kind: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=4000)
    severity: str = Field(default="error", pattern=r"^(warning|error)$")


class SourceFlowDefinitionInput(StrictDataMcpContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=100)
    name: str = Field(min_length=1, max_length=200)
    source_kind: DataSourceKind
    source_configuration: dict[str, object] = Field(default_factory=dict)
    secret_reference: str | None = Field(default=None, max_length=500)
    connector: SourceConnectorInput
    classification: DataClassification = DataClassification.INTERNAL
    contract_version: str = Field(
        default="1.0.0",
        pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
    )
    schema_document: dict[str, object]
    quality_rules: tuple[SourceQualityRuleInput, ...] = Field(default=(), max_length=100)
    freshness_minutes: int | None = Field(default=None, ge=1)
    retention_days: int | None = Field(default=None, ge=1)
    schedule: SourceScheduleInput | None = None
    activate: bool = True


class SourceScheduleDetail(StrictDataMcpContract):
    interval_minutes: int
    next_run_at: datetime
    enabled: bool
    revision: int
    last_claimed_at: datetime | None


class SourceFlowDetail(StrictDataMcpContract):
    key: str
    name: str
    status: DataStatus
    revision: int
    source_kind: DataSourceKind
    has_credentials: bool
    asset_key: str
    classification: DataClassification
    contract_version: str
    schedule: SourceScheduleDetail | None
    active_unit: str
    correlation_id: UUID

    @classmethod
    def from_domain(
        cls, flow: SourceFlow, *, active_unit: str, correlation_id: UUID
    ) -> SourceFlowDetail:
        schedule = flow.schedule
        return cls(
            key=flow.key,
            name=flow.pipeline.name,
            status=flow.status,
            revision=flow.revision,
            source_kind=flow.source.kind,
            has_credentials=flow.source.secret_reference is not None,
            asset_key=flow.asset.key,
            classification=flow.asset.classification,
            contract_version=flow.contract.version,
            schedule=(
                SourceScheduleDetail(
                    interval_minutes=schedule.interval_minutes,
                    next_run_at=schedule.next_run_at,
                    enabled=schedule.enabled,
                    revision=schedule.revision,
                    last_claimed_at=schedule.last_claimed_at,
                )
                if schedule is not None
                else None
            ),
            active_unit=active_unit,
            correlation_id=correlation_id,
        )


class SourceFlowHealthDetail(StrictDataMcpContract):
    flow: SourceFlowDetail
    latest_run_status: str | None
    latest_snapshot_id: UUID | None
    latest_snapshot_observed_at: datetime | None
    quality_status: str | None

    @classmethod
    def from_domain(
        cls, health: SourceFlowHealth, *, active_unit: str, correlation_id: UUID
    ) -> SourceFlowHealthDetail:
        return cls(
            flow=SourceFlowDetail.from_domain(
                health.flow, active_unit=active_unit, correlation_id=correlation_id
            ),
            latest_run_status=(
                health.latest_run.status.value if health.latest_run is not None else None
            ),
            latest_snapshot_id=health.latest_snapshot_id,
            latest_snapshot_observed_at=health.latest_snapshot_observed_at,
            quality_status=health.quality_status,
        )


DATA_TOOLS: tuple[RegistryTool, ...] = (
    RegistryTool("discover_data_assets", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_data_asset", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_data_contract", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("list_data_snapshots", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("trace_data_lineage", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_ingestion_run", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool(
        "search_data_content",
        "data:content:read",
        "can_view",
        "org_unit",
        RegistryRisk.READ,
    ),
    RegistryTool(
        "get_data_excerpt",
        "data:content:read",
        "can_view",
        "org_unit",
        RegistryRisk.READ,
    ),
    RegistryTool(
        "start_ingestion",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "get_source_flow_health",
        "data:read",
        "can_view",
        "org_unit",
        RegistryRisk.READ,
    ),
    RegistryTool(
        "configure_source_flow",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "set_source_flow_state",
        "data:ingest",
        "can_manage",
        "org_unit",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "schedule_source_flow",
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
    "DATA_TOOLS",
    "ContentCitation",
    "ContentExcerptResult",
    "ContentHitDetail",
    "ContentSearchResult",
    "DataAssetDetail",
    "DataAssetSummary",
    "DataContractDetail",
    "DataDiscoveryResult",
    "IngestionAccepted",
    "IngestionRunDetail",
    "LineageResult",
    "QualityResultDetail",
    "SnapshotListResult",
    "SnapshotSummary",
    "SourceFlowDefinitionInput",
    "SourceFlowDetail",
    "SourceFlowHealthDetail",
    "SourceQualityRuleInput",
    "SourceScheduleInput",
]
