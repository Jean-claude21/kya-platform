"""Strict, secret-safe schemas for governed Data MCP tools."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataSnapshot,
    DataStatus,
    QualityResult,
)
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


DATA_TOOLS: tuple[RegistryTool, ...] = (
    RegistryTool("discover_data_assets", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_data_asset", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_data_contract", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("list_data_snapshots", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("trace_data_lineage", "data:read", "can_view", "org_unit", RegistryRisk.READ),
    RegistryTool("get_ingestion_run", "data:read", "can_view", "org_unit", RegistryRisk.READ),
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
)


__all__ = [
    "DATA_TOOLS",
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
]
