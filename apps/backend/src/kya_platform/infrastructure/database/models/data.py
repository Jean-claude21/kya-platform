"""Operational metadata for governed ingestion and data products."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class DataSourceRow(Base):
    __tablename__ = "source"
    __table_args__ = (
        UniqueConstraint("key", name="uq_data_source_key"),
        CheckConstraint(
            "kind IN ('web','api','database','file','stream','manual')", name="valid_kind"
        ),
        CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        Index("ix_data_source_owner", "owner_unit_id", "status"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    system_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog.artifact.id", ondelete="RESTRICT"), nullable=True
    )
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataAssetRow(Base):
    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("key", name="uq_data_asset_key"),
        CheckConstraint("layer IN ('raw','standardized','curated','product')", name="valid_layer"),
        CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="valid_classification",
        ),
        CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        Index("ix_data_asset_owner", "owner_unit_id", "status"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataContractVersionRow(Base):
    __tablename__ = "contract_version"
    __table_args__ = (
        UniqueConstraint("asset_id", "version", name="uq_data_contract_asset_version"),
        UniqueConstraint("asset_id", "digest", name="uq_data_contract_asset_digest"),
        CheckConstraint(
            "freshness_minutes IS NULL OR freshness_minutes > 0", name="valid_freshness"
        ),
        CheckConstraint("retention_days IS NULL OR retention_days > 0", name="valid_retention"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.asset.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    quality_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    freshness_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataPipelineRow(Base):
    __tablename__ = "pipeline"
    __table_args__ = (
        UniqueConstraint("key", name="uq_data_pipeline_key"),
        CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        Index("ix_data_pipeline_owner", "owner_unit_id", "status"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.source.id", ondelete="RESTRICT"), nullable=False
    )
    connector_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog.artifact_version.id", ondelete="RESTRICT"), nullable=False
    )
    output_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.asset.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataIngestionRunRow(Base):
    __tablename__ = "ingestion_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started','completed','failed','aborted')", name="valid_status"
        ),
        CheckConstraint("completed_at IS NULL OR completed_at >= started_at", name="valid_period"),
        CheckConstraint(
            "(status = 'started' AND completed_at IS NULL) OR "
            "(status <> 'started' AND completed_at IS NOT NULL)",
            name="valid_completion",
        ),
        Index("ix_data_run_pipeline_started", "pipeline_id", "started_at"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.pipeline.id", ondelete="RESTRICT"), nullable=False
    )
    triggered_by: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_cursor: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)


class DataSnapshotRow(Base):
    __tablename__ = "snapshot"
    __table_args__ = (
        UniqueConstraint("asset_id", "run_id", name="uq_data_snapshot_asset_run"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="valid_row_count"),
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="valid_byte_size"),
        Index("ix_data_snapshot_asset_observed", "asset_id", "observed_at"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.asset.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.ingestion_run.id", ondelete="RESTRICT"), nullable=False
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.contract_version.id", ondelete="RESTRICT"), nullable=False
    )
    storage_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_container: Mapped[str] = mapped_column(String(240), nullable=False)
    object_key: Mapped[str] = mapped_column(String(800), nullable=False)
    object_version: Mapped[str | None] = mapped_column(String(240), nullable=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(160), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataLineageEdgeRow(Base):
    __tablename__ = "lineage_edge"
    __table_args__ = (
        CheckConstraint("input_snapshot_id <> output_snapshot_id", name="different_snapshots"),
        {"schema": "data"},
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.ingestion_run.id", ondelete="RESTRICT"), primary_key=True
    )
    input_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    output_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.snapshot.id", ondelete="RESTRICT"), primary_key=True
    )


class DataQualityResultRow(Base):
    __tablename__ = "quality_result"
    __table_args__ = (
        CheckConstraint("status IN ('passed','warning','failed')", name="valid_status"),
        {"schema": "data"},
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    rule_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class DataContentDocumentRow(Base):
    __tablename__ = "content_document"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "ordinal", name="uq_data_content_document_ordinal"),
        UniqueConstraint("snapshot_id", "source_uri", name="uq_data_content_document_source"),
        CheckConstraint("ordinal >= 0", name="valid_ordinal"),
        CheckConstraint("content_trust = 'untrusted_external_content'", name="valid_content_trust"),
        Index("ix_data_content_document_snapshot", "snapshot_id"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.snapshot.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1200), nullable=False)
    canonical_uri: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_trust: Mapped[str] = mapped_column(String(64), nullable=False)


class DataContentChunkRow(Base):
    __tablename__ = "content_chunk"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_data_content_chunk_ordinal"),
        CheckConstraint("ordinal >= 0", name="valid_ordinal"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="valid_character_range"),
        Index("ix_data_content_chunk_document", "document_id"),
        Index("ix_data_content_chunk_search", "search_vector", postgresql_using="gin"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.content_document.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', text)", persisted=True),
        nullable=False,
    )


__all__ = [
    "DataAssetRow",
    "DataContentChunkRow",
    "DataContentDocumentRow",
    "DataContractVersionRow",
    "DataIngestionRunRow",
    "DataLineageEdgeRow",
    "DataPipelineRow",
    "DataQualityResultRow",
    "DataSnapshotRow",
    "DataSourceRow",
]
