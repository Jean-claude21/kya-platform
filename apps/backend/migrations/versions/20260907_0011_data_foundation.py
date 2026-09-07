"""Create KYA Data Foundation control-plane metadata.

Revision ID: 20260907_0011
Revises: 20260907_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0011"
down_revision: str | None = "20260907_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS data")
    op.create_table(
        "source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("owner_unit_id", sa.Uuid(), nullable=False),
        sa.Column("system_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("secret_reference", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('web','api','database','file','stream','manual')", name="valid_kind"
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["owner_unit_id"], ["core.organizational_unit.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["system_artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_data_source_key"),
        schema="data",
    )
    op.create_index("ix_data_source_owner", "source", ["owner_unit_id", "status"], schema="data")

    op.create_table(
        "asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("owner_unit_id", sa.Uuid(), nullable=False),
        sa.Column("layer", sa.String(32), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "layer IN ('raw','standardized','curated','product')", name="valid_layer"
        ),
        sa.CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="valid_classification",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["owner_unit_id"], ["core.organizational_unit.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_data_asset_key"),
        schema="data",
    )
    op.create_index("ix_data_asset_owner", "asset", ["owner_unit_id", "status"], schema="data")

    op.create_table(
        "contract_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("schema_document", postgresql.JSONB(), nullable=False),
        sa.Column("quality_rules", postgresql.JSONB(), nullable=False),
        sa.Column("freshness_minutes", sa.Integer(), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "freshness_minutes IS NULL OR freshness_minutes > 0", name="valid_freshness"
        ),
        sa.CheckConstraint("retention_days IS NULL OR retention_days > 0", name="valid_retention"),
        sa.ForeignKeyConstraint(["asset_id"], ["data.asset.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "digest", name="uq_data_contract_asset_digest"),
        sa.UniqueConstraint("asset_id", "version", name="uq_data_contract_asset_version"),
        schema="data",
    )

    op.create_table(
        "pipeline",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("owner_unit_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("connector_version_id", sa.Uuid(), nullable=False),
        sa.Column("output_asset_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','deprecated','retired')", name="valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["connector_version_id"], ["catalog.artifact_version.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["output_asset_id"], ["data.asset.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_unit_id"], ["core.organizational_unit.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["data.source.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_data_pipeline_key"),
        schema="data",
    )
    op.create_index(
        "ix_data_pipeline_owner", "pipeline", ["owner_unit_id", "status"], schema="data"
    )

    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_cursor", postgresql.JSONB(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.CheckConstraint(
            "status IN ('started','completed','failed','aborted')", name="valid_status"
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="valid_period"
        ),
        sa.CheckConstraint(
            "(status = 'started' AND completed_at IS NULL) OR "
            "(status <> 'started' AND completed_at IS NOT NULL)",
            name="valid_completion",
        ),
        sa.ForeignKeyConstraint(["pipeline_id"], ["data.pipeline.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema="data",
    )
    op.create_index(
        "ix_data_run_pipeline_started",
        "ingestion_run",
        ["pipeline_id", "started_at"],
        schema="data",
    )

    op.create_table(
        "snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("storage_provider", sa.String(80), nullable=False),
        sa.Column("storage_container", sa.String(240), nullable=False),
        sa.Column("object_key", sa.String(800), nullable=False),
        sa.Column("object_version", sa.String(240), nullable=True),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(160), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("row_count IS NULL OR row_count >= 0", name="valid_row_count"),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="valid_byte_size"),
        sa.ForeignKeyConstraint(["asset_id"], ["data.asset.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["data.contract_version.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["data.ingestion_run.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "run_id", name="uq_data_snapshot_asset_run"),
        schema="data",
    )
    op.create_index(
        "ix_data_snapshot_asset_observed",
        "snapshot",
        ["asset_id", "observed_at"],
        schema="data",
    )

    op.create_table(
        "lineage_edge",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("input_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("output_snapshot_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("input_snapshot_id <> output_snapshot_id", name="different_snapshots"),
        sa.ForeignKeyConstraint(["input_snapshot_id"], ["data.snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_snapshot_id"], ["data.snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["data.ingestion_run.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id", "input_snapshot_id", "output_snapshot_id"),
        schema="data",
    )

    op.create_table(
        "quality_result",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("observed", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("status IN ('passed','warning','failed')", name="valid_status"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["data.snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("snapshot_id", "rule_key"),
        schema="data",
    )


def downgrade() -> None:
    op.drop_table("quality_result", schema="data")
    op.drop_table("lineage_edge", schema="data")
    op.drop_index("ix_data_snapshot_asset_observed", table_name="snapshot", schema="data")
    op.drop_table("snapshot", schema="data")
    op.drop_index("ix_data_run_pipeline_started", table_name="ingestion_run", schema="data")
    op.drop_table("ingestion_run", schema="data")
    op.drop_index("ix_data_pipeline_owner", table_name="pipeline", schema="data")
    op.drop_table("pipeline", schema="data")
    op.drop_table("contract_version", schema="data")
    op.drop_index("ix_data_asset_owner", table_name="asset", schema="data")
    op.drop_table("asset", schema="data")
    op.drop_index("ix_data_source_owner", table_name="source", schema="data")
    op.drop_table("source", schema="data")
    op.execute("DROP SCHEMA IF EXISTS data")
