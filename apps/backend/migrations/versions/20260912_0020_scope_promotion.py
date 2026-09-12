"""Add the scope promotion workflow table.

Revision ID: 20260912_0020
Revises: 20260911_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0020"
down_revision: str | None = "20260911_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scope_promotion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("current_scope_unit_id", sa.Uuid(), nullable=False),
        sa.Column("target_scope_unit_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("separation_of_duties", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_decision", sa.String(length=32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("approval_decision", sa.String(length=32), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.Uuid(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('awaiting-review', 'awaiting-approval', 'approved', 'rejected', 'applied')",
            name="ck_catalog_scope_promotion_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["catalog.artifact.id"],
            ondelete="RESTRICT",
            name="fk_catalog_scope_promotion_artifact_id_artifact",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_scope_promotion"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_scope_promotion_artifact",
        "scope_promotion",
        ["artifact_id", "requested_at"],
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_scope_promotion_artifact", table_name="scope_promotion", schema="catalog"
    )
    op.drop_table("scope_promotion", schema="catalog")
