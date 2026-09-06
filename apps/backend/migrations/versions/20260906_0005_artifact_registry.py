"""Add the governed multi-file artifact registry.

Revision ID: 20260906_0005
Revises: 20260905_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260906_0005"
down_revision: str | None = "20260905_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS catalog")
    op.create_table(
        "artifact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registry_id", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("owner_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("business_owner_id", sa.Uuid(), nullable=False),
        sa.Column("technical_owner_id", sa.Uuid(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'prototype', 'candidate', 'validating', 'approved', "
            "'published', 'suspended', 'deprecated', 'retired')",
            name="ck_artifact_valid_lifecycle",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifact"),
        sa.UniqueConstraint("registry_id", "slug", name="uq_catalog_artifact_registry_slug"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_artifact_owner_workspace",
        "artifact",
        ["owner_workspace_id"],
        schema="catalog",
    )
    op.create_table(
        "artifact_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_repository", sa.String(length=500), nullable=False),
        sa.Column("source_commit", sa.String(length=40), nullable=False),
        sa.Column("source_path", sa.String(length=512), nullable=True),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size", sa.Integer(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("has_executable_content", sa.Boolean(), nullable=False),
        sa.Column("risk", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "package_size >= 0", name="ck_artifact_version_nonnegative_package_size"
        ),
        sa.CheckConstraint(
            "file_count > 0 AND file_count <= 2000", name="ck_artifact_version_valid_file_count"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'candidate', 'validating', 'approved', 'published', "
            "'suspended', 'revoked')",
            name="ck_artifact_version_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["catalog.artifact.id"],
            ondelete="RESTRICT",
            name="fk_artifact_version_artifact_id_artifact",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_version"),
        sa.UniqueConstraint("artifact_id", "version", name="uq_catalog_version_artifact_semver"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_version_content_digest",
        "artifact_version",
        ["content_digest"],
        schema="catalog",
    )
    op.create_table(
        "package_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False),
        sa.CheckConstraint("size >= 0", name="ck_package_file_nonnegative_size"),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["catalog.artifact_version.id"],
            ondelete="CASCADE",
            name="fk_package_file_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_package_file"),
        sa.UniqueConstraint("version_id", "path", name="uq_catalog_package_file_version_path"),
        schema="catalog",
    )
    op.create_table(
        "capability_manifest",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("runtime", sa.String(length=100), nullable=False),
        sa.Column("declaration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["catalog.artifact_version.id"],
            ondelete="CASCADE",
            name="fk_capability_manifest_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("version_id", name="pk_capability_manifest"),
        schema="catalog",
    )
    op.execute(
        """
        CREATE FUNCTION catalog.reject_published_version_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status = 'published' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'published artifact versions are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_published_version_immutable
        BEFORE UPDATE OR DELETE ON catalog.artifact_version
        FOR EACH ROW EXECUTE FUNCTION catalog.reject_published_version_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_published_version_immutable ON catalog.artifact_version"
    )
    op.execute("DROP FUNCTION IF EXISTS catalog.reject_published_version_mutation()")
    op.drop_table("capability_manifest", schema="catalog")
    op.drop_table("package_file", schema="catalog")
    op.drop_index(
        "ix_catalog_version_content_digest", table_name="artifact_version", schema="catalog"
    )
    op.drop_table("artifact_version", schema="catalog")
    op.drop_index("ix_catalog_artifact_owner_workspace", table_name="artifact", schema="catalog")
    op.drop_table("artifact", schema="catalog")
    op.execute("DROP SCHEMA IF EXISTS catalog")
