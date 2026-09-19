"""Persist immutable native document definitions, records and evidence.

Revision ID: 20260919_0025
Revises: 20260918_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_0025"
down_revision: str | None = "20260918_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS documents")
    op.create_table(
        "definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(240), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("owner_scope", sa.String(255), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("digest", name="uq_document_definition_digest"),
        sa.UniqueConstraint("public_id", "version", name="uq_document_definition_public_version"),
        sa.UniqueConstraint("release_id", name="uq_document_definition_release"),
        schema="documents",
    )
    op.create_index(
        "ix_document_definition_scope",
        "definition",
        ["owner_scope", "public_id"],
        schema="documents",
    )
    op.create_table(
        "record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("owner_scope", sa.String(255), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("current_revision > 0", name="positive_revision"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["documents.definition.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="documents",
    )
    op.create_index(
        "ix_document_record_scope_state",
        "record",
        ["owner_scope", "state", "updated_at"],
        schema="documents",
    )
    op.create_index(
        "ix_document_record_definition",
        "record",
        ["definition_id", "created_at"],
        schema="documents",
    )
    op.create_table(
        "revision",
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("authored_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.ForeignKeyConstraint(["record_id"], ["documents.record.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("record_id", "revision"),
        sa.UniqueConstraint("record_id", "digest", name="uq_document_revision_record_digest"),
        schema="documents",
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint(
            "kind IN ('transition','signature','attachment','notification')", name="valid_kind"
        ),
        sa.ForeignKeyConstraint(["record_id"], ["documents.record.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id", "digest", name="uq_document_evidence_record_digest"),
        schema="documents",
    )
    op.create_index(
        "ix_document_evidence_record_time",
        "evidence",
        ["record_id", "occurred_at"],
        schema="documents",
    )


def downgrade() -> None:
    op.drop_index("ix_document_evidence_record_time", table_name="evidence", schema="documents")
    op.drop_table("evidence", schema="documents")
    op.drop_table("revision", schema="documents")
    op.drop_index("ix_document_record_definition", table_name="record", schema="documents")
    op.drop_index("ix_document_record_scope_state", table_name="record", schema="documents")
    op.drop_table("record", schema="documents")
    op.drop_index("ix_document_definition_scope", table_name="definition", schema="documents")
    op.drop_table("definition", schema="documents")
    op.execute("DROP SCHEMA IF EXISTS documents")
