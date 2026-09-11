"""Add secret reference governance metadata.

Revision ID: 20260911_0018
Revises: 20260910_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0018"
down_revision: str | None = "20260910_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "secret_reference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("locator", sa.String(length=512), nullable=False),
        sa.Column("key_name", sa.String(length=128), nullable=False),
        sa.Column("owner_scope", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('personal', 'team', 'service', 'application', 'environment')",
            name="ck_secret_reference_valid_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'rotation_due', 'revoked')",
            name="ck_secret_reference_valid_status",
        ),
        sa.CheckConstraint(
            "environment IN ('local', 'preview', 'test', 'production')",
            name="ck_secret_reference_valid_environment",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_secret_reference_owner_scope", "secret_reference", ["owner_scope"], schema="core"
    )


def downgrade() -> None:
    op.drop_index("ix_secret_reference_owner_scope", table_name="secret_reference", schema="core")
    op.drop_table("secret_reference", schema="core")

