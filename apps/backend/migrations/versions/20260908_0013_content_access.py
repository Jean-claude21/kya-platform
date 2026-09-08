"""Add reconstructible, citation-ready content projections.

Revision ID: 20260908_0013
Revises: 20260908_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0013"
down_revision: str | None = "20260908_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_document",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_uri", sa.String(1200), nullable=False),
        sa.Column("canonical_uri", sa.String(1200), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("body_digest", sa.String(64), nullable=False),
        sa.Column("content_trust", sa.String(64), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="valid_ordinal"),
        sa.CheckConstraint(
            "content_trust = 'untrusted_external_content'", name="valid_content_trust"
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["data.snapshot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "ordinal", name="uq_data_content_document_ordinal"),
        sa.UniqueConstraint("snapshot_id", "source_uri", name="uq_data_content_document_source"),
        schema="data",
    )
    op.create_index(
        "ix_data_content_document_snapshot",
        "content_document",
        ["snapshot_id"],
        schema="data",
    )
    op.create_table(
        "content_chunk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint("ordinal >= 0", name="valid_ordinal"),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start", name="valid_character_range"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["data.content_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_data_content_chunk_ordinal"),
        schema="data",
    )
    op.create_index(
        "ix_data_content_chunk_document",
        "content_chunk",
        ["document_id"],
        schema="data",
    )
    op.create_index(
        "ix_data_content_chunk_search",
        "content_chunk",
        ["search_vector"],
        postgresql_using="gin",
        schema="data",
    )


def downgrade() -> None:
    op.drop_index("ix_data_content_chunk_search", table_name="content_chunk", schema="data")
    op.drop_index("ix_data_content_chunk_document", table_name="content_chunk", schema="data")
    op.drop_table("content_chunk", schema="data")
    op.drop_index("ix_data_content_document_snapshot", table_name="content_document", schema="data")
    op.drop_table("content_document", schema="data")
