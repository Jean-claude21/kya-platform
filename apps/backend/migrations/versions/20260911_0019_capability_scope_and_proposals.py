"""Add capability visibility scope, discoverability and non-developer proposals.

Revision ID: 20260911_0019
Revises: 20260911_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0019"
down_revision: str | None = "20260911_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artifact",
        sa.Column("visibility_scope_unit_id", sa.Uuid(), nullable=True),
        schema="catalog",
    )
    op.add_column(
        "artifact",
        sa.Column(
            "discoverable", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_artifact_visibility_scope_unit",
        "artifact",
        ["visibility_scope_unit_id"],
        schema="catalog",
    )
    op.create_table(
        "proposal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("target_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("package", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_decision", sa.String(length=32), nullable=True),
        sa.Column("review_reason", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pull_request_url", sa.String(length=700), nullable=True),
        sa.Column("merged_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("resulting_artifact_version_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('submitted', 'in_review', 'approved', 'rejected', 'pull_request_open', "
            "'merged', 'closed_without_merge')",
            name="ck_catalog_proposal_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["catalog.artifact.id"],
            ondelete="RESTRICT",
            name="fk_catalog_proposal_artifact_id_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_artifact_version_id"],
            ["catalog.artifact_version.id"],
            ondelete="RESTRICT",
            name="fk_catalog_proposal_resulting_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_proposal"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_proposal_target_workspace",
        "proposal",
        ["target_workspace_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_proposal_requested_by_status",
        "proposal",
        ["requested_by", "status"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_proposal_artifact", "proposal", ["artifact_id"], schema="catalog"
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_proposal_artifact", table_name="proposal", schema="catalog")
    op.drop_index(
        "ix_catalog_proposal_requested_by_status", table_name="proposal", schema="catalog"
    )
    op.drop_index(
        "ix_catalog_proposal_target_workspace", table_name="proposal", schema="catalog"
    )
    op.drop_table("proposal", schema="catalog")
    op.drop_index(
        "ix_catalog_artifact_visibility_scope_unit", table_name="artifact", schema="catalog"
    )
    op.drop_column("artifact", "discoverable", schema="catalog")
    op.drop_column("artifact", "visibility_scope_unit_id", schema="catalog")