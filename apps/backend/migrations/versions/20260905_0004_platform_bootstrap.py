"""Add the recoverable singleton platform-owner bootstrap claim.

Revision ID: 20260905_0004
Revises: 20260904_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0004"
down_revision: str | None = "20260904_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_bootstrap_claim",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("owner_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column(
            "reserved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state IN ('reserved', 'complete')", name="ck_platform_bootstrap_claim_valid_state"),
        sa.PrimaryKeyConstraint("key", name="pk_platform_bootstrap_claim"),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_table("platform_bootstrap_claim", schema="identity")
