"""Add governed intelligence watchlists and signals.

Revision ID: 20260908_0016
Revises: 20260908_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0016"
down_revision: str | None = "20260908_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS intelligence")
    op.create_table(
        "watch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("owner_unit_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("asset_keys", postgresql.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint("status IN ('active','paused')", name="valid_status"),
        sa.ForeignKeyConstraint(
            ["owner_unit_id"], ["core.organizational_unit.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_unit_id", "key", name="uq_intelligence_watch_unit_key"),
        schema="intelligence",
    )
    op.create_index(
        "ix_intelligence_watch_unit_status",
        "watch",
        ["owner_unit_id", "status"],
        schema="intelligence",
    )
    op.create_table(
        "signal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("watch_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("citation_id", sa.String(length=240), nullable=False),
        sa.Column("source_uri", sa.String(length=1200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("page_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("acknowledged_by", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint("status IN ('open','acknowledged')", name="valid_status"),
        sa.ForeignKeyConstraint(["chunk_id"], ["data.content_chunk.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["data.snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["watch_id"], ["intelligence.watch.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watch_id", "chunk_id", name="uq_intelligence_signal_watch_chunk"),
        schema="intelligence",
    )
    op.create_index(
        "ix_intelligence_signal_watch_status",
        "signal",
        ["watch_id", "status", "observed_at"],
        schema="intelligence",
    )


def downgrade() -> None:
    op.drop_index("ix_intelligence_signal_watch_status", table_name="signal", schema="intelligence")
    op.drop_table("signal", schema="intelligence")
    op.drop_index("ix_intelligence_watch_unit_status", table_name="watch", schema="intelligence")
    op.drop_table("watch", schema="intelligence")
    op.execute("DROP SCHEMA IF EXISTS intelligence")
