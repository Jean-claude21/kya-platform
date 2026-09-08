"""Add governed MCP tool profiles and restrictive user preferences.

Revision ID: 20260908_0014
Revises: 20260908_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0014"
down_revision: str | None = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mcp_control")
    op.create_table(
        "tool_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("oauth_scope", sa.String(120), nullable=False),
        sa.Column("target_object_type", sa.String(80), nullable=False),
        sa.Column("target_relation", sa.String(80), nullable=False),
        sa.Column("risk", sa.String(32), nullable=False),
        sa.Column("is_write", sa.Boolean(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("requires_idempotency", sa.Boolean(), nullable=False),
        sa.Column("handler_key", sa.String(160), nullable=False),
        sa.Column("input_schema_digest", sa.String(64), nullable=True),
        sa.Column("output_schema_digest", sa.String(64), nullable=True),
        sa.Column("lifecycle_state", sa.String(24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "risk IN ('read', 'controlled-write', 'sensitive-write')", name="valid_risk"
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('draft', 'active', 'retired')",
            name="valid_lifecycle_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handler_key", name="uq_mcp_tool_definition_handler"),
        sa.UniqueConstraint("key", name="uq_mcp_tool_definition_key"),
        schema="mcp_control",
    )
    op.create_table(
        "tool_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("owner_unit_key", sa.String(512), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("max_active_tools", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('system', 'business', 'personal-template')", name="valid_kind"
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="valid_status"),
        sa.CheckConstraint("version > 0 AND revision > 0", name="positive_versions"),
        sa.CheckConstraint(
            "max_active_tools > 0 AND max_active_tools <= 24", name="valid_max_active_tools"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_mcp_tool_profile_key"),
        schema="mcp_control",
    )
    op.create_table(
        "tool_profile_item",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("configured_by", sa.Uuid(), nullable=False),
        sa.Column(
            "configured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        sa.CheckConstraint("state IN ('enabled', 'disabled')", name="valid_state"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["mcp_control.tool_profile.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["mcp_control.tool_definition.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("profile_id", "tool_id"),
        schema="mcp_control",
    )
    op.create_table(
        "tool_profile_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(24), nullable=False),
        sa.Column("subject_key", sa.String(512), nullable=False),
        sa.Column("context_unit_key", sa.String(512), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject_type IN ('user', 'team', 'role', 'org_unit')", name="valid_subject_type"
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_validity_window"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["mcp_control.tool_profile.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="mcp_control",
    )
    op.create_index(
        "ix_mcp_profile_assignment_subject",
        "tool_profile_assignment",
        ["subject_type", "subject_key", "context_unit_key", "valid_from", "valid_until"],
        schema="mcp_control",
    )
    op.create_table(
        "user_tool_preference",
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("active_unit_key", sa.String(512), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint("state = 'disabled'", name="restrictive_state_only"),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["mcp_control.tool_definition.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("principal_id", "active_unit_key", "client_id", "tool_id"),
        schema="mcp_control",
    )
    op.create_index(
        "ix_mcp_user_preference_context",
        "user_tool_preference",
        ["principal_id", "active_unit_key"],
        schema="mcp_control",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mcp_user_preference_context",
        table_name="user_tool_preference",
        schema="mcp_control",
    )
    op.drop_table("user_tool_preference", schema="mcp_control")
    op.drop_index(
        "ix_mcp_profile_assignment_subject",
        table_name="tool_profile_assignment",
        schema="mcp_control",
    )
    op.drop_table("tool_profile_assignment", schema="mcp_control")
    op.drop_table("tool_profile_item", schema="mcp_control")
    op.drop_table("tool_profile", schema="mcp_control")
    op.drop_table("tool_definition", schema="mcp_control")
    op.execute("DROP SCHEMA IF EXISTS mcp_control")
