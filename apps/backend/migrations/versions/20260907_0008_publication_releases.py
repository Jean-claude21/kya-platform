"""Persist governed publication requests and signed releases.

Revision ID: 20260907_0008
Revises: 20260907_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0008"
down_revision: str | None = "20260907_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attestation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("predicate_type", sa.String(length=300), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("issuer_id", sa.Uuid(), nullable=False),
        sa.Column("subject_digest", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_uri", sa.String(length=700), nullable=False),
        sa.CheckConstraint("result IN ('passed', 'failed')", name="ck_attestation_valid_result"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_attestation_validity_window",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["catalog.artifact_version.id"],
            ondelete="RESTRICT",
            name="fk_attestation_artifact_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attestation"),
        sa.UniqueConstraint(
            "artifact_version_id",
            "kind",
            "issuer_id",
            "digest",
            name="uq_catalog_attestation_issuer_kind_digest",
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_attestation_version",
        "attestation",
        ["artifact_version_id"],
        schema="catalog",
    )
    op.execute(
        """
        CREATE FUNCTION catalog.reject_attestation_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'publication attestations are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_attestation_immutable
        BEFORE UPDATE OR DELETE ON catalog.attestation
        FOR EACH ROW EXECUTE FUNCTION catalog.reject_attestation_mutation()
        """
    )
    op.create_table(
        "publication_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("separation_of_duties", sa.Boolean(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_decision", sa.String(length=32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("approval_decision", sa.String(length=32), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('awaiting-review', 'awaiting-approval', 'approved', 'rejected', "
            "'published')",
            name="ck_publication_request_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["catalog.artifact.id"],
            ondelete="RESTRICT",
            name="fk_publication_request_artifact_id_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["catalog.artifact_version.id"],
            ondelete="RESTRICT",
            name="fk_publication_request_artifact_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication_request"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_publication_artifact",
        "publication_request",
        ["artifact_id", "requested_at"],
        schema="catalog",
    )
    op.execute(
        """
        CREATE FUNCTION catalog.reject_publication_candidate_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.artifact_id IS DISTINCT FROM OLD.artifact_id
             OR NEW.artifact_version_id IS DISTINCT FROM OLD.artifact_version_id
             OR NEW.version IS DISTINCT FROM OLD.version
             OR NEW.commit_sha IS DISTINCT FROM OLD.commit_sha
             OR NEW.content_digest IS DISTINCT FROM OLD.content_digest
             OR NEW.manifest_digest IS DISTINCT FROM OLD.manifest_digest
             OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
             OR NEW.requested_at IS DISTINCT FROM OLD.requested_at
             OR NEW.separation_of_duties IS DISTINCT FROM OLD.separation_of_duties
             OR NEW.evidence_ids IS DISTINCT FROM OLD.evidence_ids THEN
            RAISE EXCEPTION 'publication candidate and evidence are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_publication_candidate_immutable
        BEFORE UPDATE ON catalog.publication_request
        FOR EACH ROW EXECUTE FUNCTION catalog.reject_publication_candidate_mutation()
        """
    )
    op.create_table(
        "release",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("signature", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("storage_locator", sa.String(length=700), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=False),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('published', 'suspended', 'revoked')",
            name="ck_release_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["catalog.artifact_version.id"],
            ondelete="RESTRICT",
            name="fk_release_artifact_version_id_artifact_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_release"),
        sa.UniqueConstraint("artifact_version_id", name="uq_catalog_release_artifact_version"),
        schema="catalog",
    )
    op.create_index("ix_catalog_release_digest", "release", ["content_digest"], schema="catalog")
    op.execute(
        """
        CREATE FUNCTION catalog.reject_release_integrity_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.artifact_version_id IS DISTINCT FROM OLD.artifact_version_id
             OR NEW.content_digest IS DISTINCT FROM OLD.content_digest
             OR NEW.signature IS DISTINCT FROM OLD.signature
             OR NEW.storage_locator IS DISTINCT FROM OLD.storage_locator
             OR NEW.published_at IS DISTINCT FROM OLD.published_at
             OR NEW.published_by IS DISTINCT FROM OLD.published_by THEN
            RAISE EXCEPTION 'published release integrity fields are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_catalog_release_integrity_immutable
        BEFORE UPDATE ON catalog.release
        FOR EACH ROW EXECUTE FUNCTION catalog.reject_release_integrity_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_catalog_release_integrity_immutable ON catalog.release")
    op.execute("DROP FUNCTION IF EXISTS catalog.reject_release_integrity_mutation()")
    op.drop_index("ix_catalog_release_digest", table_name="release", schema="catalog")
    op.drop_table("release", schema="catalog")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_publication_candidate_immutable "
        "ON catalog.publication_request"
    )
    op.execute("DROP FUNCTION IF EXISTS catalog.reject_publication_candidate_mutation()")
    op.drop_index(
        "ix_catalog_publication_artifact",
        table_name="publication_request",
        schema="catalog",
    )
    op.drop_table("publication_request", schema="catalog")
    op.execute("DROP TRIGGER IF EXISTS trg_catalog_attestation_immutable ON catalog.attestation")
    op.execute("DROP FUNCTION IF EXISTS catalog.reject_attestation_mutation()")
    op.drop_index("ix_catalog_attestation_version", table_name="attestation", schema="catalog")
    op.drop_table("attestation", schema="catalog")
