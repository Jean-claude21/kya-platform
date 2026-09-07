"""Persist installations, lifecycle history and idempotent operations.

Revision ID: 20260907_0009
Revises: 20260907_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0009"
down_revision: str | None = "20260907_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("client_version", sa.String(length=64), nullable=False),
        sa.Column("active_release_id", sa.Uuid(), nullable=False),
        sa.Column("rollback_release_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("installed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "profile IN ('codex', 'claude-code', 'portable-zip')",
            name="ck_installation_valid_profile",
        ),
        sa.CheckConstraint("scope IN ('personal', 'project')", name="ck_installation_valid_scope"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'revoked')", name="ck_installation_valid_status"
        ),
        sa.CheckConstraint("revision > 0", name="ck_installation_positive_revision"),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["catalog.artifact.id"],
            ondelete="RESTRICT",
            name="fk_installation_artifact_id_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["active_release_id"],
            ["catalog.release.id"],
            ondelete="RESTRICT",
            name="fk_installation_active_release_id_release",
        ),
        sa.ForeignKeyConstraint(
            ["rollback_release_id"],
            ["catalog.release.id"],
            ondelete="RESTRICT",
            name="fk_installation_rollback_release_id_release",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_installation"),
        sa.UniqueConstraint(
            "artifact_id", "target", "profile", "scope", name="uq_catalog_installation_target"
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_installation_target", "installation", ["target", "status"], schema="catalog"
    )
    op.create_table(
        "installation_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_release_id", sa.Uuid(), nullable=True),
        sa.Column("to_release_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('install', 'update', 'rollback', 'suspend', 'resume', 'revoke')",
            name="ck_installation_history_valid_action",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["catalog.installation.id"],
            ondelete="RESTRICT",
            name="fk_installation_history_installation_id_installation",
        ),
        sa.ForeignKeyConstraint(
            ["from_release_id"],
            ["catalog.release.id"],
            ondelete="RESTRICT",
            name="fk_installation_history_from_release_id_release",
        ),
        sa.ForeignKeyConstraint(
            ["to_release_id"],
            ["catalog.release.id"],
            ondelete="RESTRICT",
            name="fk_installation_history_to_release_id_release",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_installation_history"),
        sa.UniqueConstraint(
            "installation_id", "sequence", name="uq_catalog_installation_history_sequence"
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_installation_history",
        "installation_history",
        ["installation_id", "sequence"],
        schema="catalog",
    )
    op.execute(
        """
        CREATE FUNCTION catalog.reject_installation_history_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'installation history is immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_installation_history_immutable
        BEFORE UPDATE OR DELETE ON catalog.installation_history
        FOR EACH ROW EXECUTE FUNCTION catalog.reject_installation_history_mutation()
        """
    )
    op.create_table(
        "distribution_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("release_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="accepted"),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('install', 'update', 'rollback', 'suspend', 'resume', 'revoke')",
            name="ck_distribution_operation_valid_kind",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'pending', 'running', 'succeeded', 'failed', 'rolled-back')",
            name="ck_distribution_operation_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["catalog.installation.id"],
            ondelete="RESTRICT",
            name="fk_distribution_operation_installation_id_installation",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["catalog.release.id"],
            ondelete="RESTRICT",
            name="fk_distribution_operation_release_id_release",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_distribution_operation"),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="uq_catalog_operation_actor_key"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_operation_installation",
        "distribution_operation",
        ["installation_id", "created_at"],
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_operation_installation", table_name="distribution_operation", schema="catalog"
    )
    op.drop_table("distribution_operation", schema="catalog")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_installation_history_immutable "
        "ON catalog.installation_history"
    )
    op.execute("DROP FUNCTION IF EXISTS catalog.reject_installation_history_mutation()")
    op.drop_index(
        "ix_catalog_installation_history", table_name="installation_history", schema="catalog"
    )
    op.drop_table("installation_history", schema="catalog")
    op.drop_index("ix_catalog_installation_target", table_name="installation", schema="catalog")
    op.drop_table("installation", schema="catalog")
