"""Add autonomous source flow revisions and durable schedules.

Revision ID: 20260908_0015
Revises: 20260908_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0015"
down_revision: str | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_flow",
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["data.pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pipeline_id"),
        schema="data",
    )
    op.create_table(
        "ingestion_schedule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "interval_minutes >= 15 AND interval_minutes <= 43200", name="valid_interval"
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["data.pipeline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_id", name="uq_data_ingestion_schedule_pipeline"),
        schema="data",
    )
    op.create_index(
        "ix_data_schedule_due",
        "ingestion_schedule",
        ["enabled", "next_run_at"],
        schema="data",
    )
    op.execute(
        """
        INSERT INTO data.source_flow (pipeline_id, revision, updated_by)
        SELECT id, 1, created_by FROM data.pipeline
        ON CONFLICT (pipeline_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_data_schedule_due", table_name="ingestion_schedule", schema="data")
    op.drop_table("ingestion_schedule", schema="data")
    op.drop_table("source_flow", schema="data")
