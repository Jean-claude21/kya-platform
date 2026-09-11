"""Add workspace boundaries and dated memberships.

Revision ID: 20260910_0017
Revises: 20260908_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0017"
down_revision: str | None = "20260908_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("owner_unit_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('personal', 'team', 'direction', 'project', 'country', 'group', "
            "'temporary', 'restricted')",
            name="ck_workspace_valid_kind",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="ck_workspace_valid_period"
        ),
        sa.ForeignKeyConstraint(
            ["owner_unit_id"], ["core.organizational_unit.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_workspace_key"),
        schema="core",
    )
    op.create_table(
        "workspace_linked_unit",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["core.workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["core.organizational_unit.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("workspace_id", "unit_id"),
        schema="core",
    )
    op.create_table(
        "workspace_membership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delegated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "level IN ('viewer', 'guest', 'member', 'contributor', 'editor', 'manager', "
            "'owner')",
            name="ck_workspace_membership_valid_level",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_workspace_membership_valid_period",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["core.workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_workspace_membership_workspace", "workspace_membership", ["workspace_id"],
        schema="core",
    )
    op.create_index(
        "ix_workspace_membership_principal", "workspace_membership", ["principal_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_membership_principal", table_name="workspace_membership", schema="core"
    )
    op.drop_index(
        "ix_workspace_membership_workspace", table_name="workspace_membership", schema="core"
    )
    op.drop_table("workspace_membership", schema="core")
    op.drop_table("workspace_linked_unit", schema="core")
    op.drop_table("workspace", schema="core")

