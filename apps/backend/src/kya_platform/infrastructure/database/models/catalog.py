"""Persistent catalog metadata; package payloads remain outside PostgreSQL."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class CatalogArtifact(Base):
    __tablename__ = "artifact"
    __table_args__ = (
        UniqueConstraint("registry_id", "slug", name="uq_catalog_artifact_registry_slug"),
        Index("ix_catalog_artifact_owner_workspace", "owner_workspace_id"),
        Index("ix_catalog_artifact_visibility_scope_unit", "visibility_scope_unit_id"),
        CheckConstraint(
            "lifecycle IN ('draft', 'prototype', 'candidate', 'validating', 'approved', "
            "'published', 'suspended', 'deprecated', 'retired')",
            name="valid_lifecycle",
        ),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    registry_id: Mapped[str] = mapped_column(String(100), nullable=False, default="kya")
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_workspace_id: Mapped[UUID] = mapped_column(nullable=False)
    business_owner_id: Mapped[UUID] = mapped_column(nullable=False)
    technical_owner_id: Mapped[UUID] = mapped_column(nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    visibility_scope_unit_id: Mapped[UUID | None] = mapped_column(nullable=True)
    discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CatalogArtifactVersion(Base):
    __tablename__ = "artifact_version"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"),
        UniqueConstraint("artifact_id", "version", name="uq_catalog_version_artifact_semver"),
        Index("ix_catalog_version_content_digest", "content_digest"),
        CheckConstraint(
            "status IN ('draft', 'candidate', 'validating', 'approved', 'published', "
            "'suspended', 'revoked')",
            name="valid_status",
        ),
        CheckConstraint("package_size >= 0", name="nonnegative_package_size"),
        CheckConstraint("file_count > 0 AND file_count <= 2000", name="valid_file_count"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    source_repository: Mapped[str] = mapped_column(String(500), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_executable_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogPackageFile(Base):
    __tablename__ = "package_file"
    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["catalog.artifact_version.id"], ondelete="CASCADE"),
        UniqueConstraint("version_id", "path", name="uq_catalog_package_file_version_path"),
        CheckConstraint("size >= 0", name="nonnegative_size"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    version_id: Mapped[UUID] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    executable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CatalogCapabilityManifest(Base):
    __tablename__ = "capability_manifest"
    __table_args__ = (
        ForeignKeyConstraint(["version_id"], ["catalog.artifact_version.id"], ondelete="CASCADE"),
        {"schema": "catalog"},
    )

    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    runtime: Mapped[str] = mapped_column(String(100), nullable=False)
    declaration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class CatalogAttestation(Base):
    __tablename__ = "attestation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_version_id"], ["catalog.artifact_version.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint(
            "artifact_version_id",
            "kind",
            "issuer_id",
            "digest",
            name="uq_catalog_attestation_issuer_kind_digest",
        ),
        Index("ix_catalog_attestation_version", "artifact_version_id"),
        CheckConstraint("result IN ('passed', 'failed')", name="valid_result"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="validity_window",
        ),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_version_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    predicate_type: Mapped[str] = mapped_column(String(300), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer_id: Mapped[UUID] = mapped_column(nullable=False)
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_uri: Mapped[str] = mapped_column(String(700), nullable=False)


class CatalogPublicationRequest(Base):
    __tablename__ = "publication_request"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["artifact_version_id"], ["catalog.artifact_version.id"], ondelete="RESTRICT"
        ),
        CheckConstraint(
            "status IN ('awaiting-review', 'awaiting-approval', 'approved', 'rejected', "
            "'published')",
            name="valid_status",
        ),
        Index("ix_catalog_publication_artifact", "artifact_id", "requested_at"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_version_id: Mapped[UUID] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    separation_of_duties: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approver_id: Mapped[UUID | None] = mapped_column(nullable=True)
    approval_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[UUID | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CatalogRelease(Base):
    __tablename__ = "release"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_version_id"], ["catalog.artifact_version.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint("artifact_version_id", name="uq_catalog_release_artifact_version"),
        CheckConstraint("status IN ('published', 'suspended', 'revoked')", name="valid_status"),
        Index("ix_catalog_release_digest", "content_digest"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_version_id: Mapped[UUID] = mapped_column(nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    storage_locator: Mapped[str] = mapped_column(String(700), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_by: Mapped[UUID] = mapped_column(nullable=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CatalogInstallation(Base):
    __tablename__ = "installation"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["active_release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["rollback_release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "artifact_id",
            "target",
            "profile",
            "scope",
            name="uq_catalog_installation_target",
        ),
        CheckConstraint(
            "profile IN ('codex', 'claude-code', 'portable-zip')", name="valid_profile"
        ),
        CheckConstraint("scope IN ('personal', 'project')", name="valid_scope"),
        CheckConstraint("status IN ('active', 'suspended', 'revoked')", name="valid_status"),
        CheckConstraint("revision > 0", name="positive_revision"),
        Index("ix_catalog_installation_target", "target", "status"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    profile: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    client_version: Mapped[str] = mapped_column(String(64), nullable=False)
    active_release_id: Mapped[UUID] = mapped_column(nullable=False)
    rollback_release_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    installed_by: Mapped[UUID] = mapped_column(nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CatalogInstallationHistory(Base):
    __tablename__ = "installation_history"
    __table_args__ = (
        ForeignKeyConstraint(["installation_id"], ["catalog.installation.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["from_release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["to_release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "installation_id", "sequence", name="uq_catalog_installation_history_sequence"
        ),
        CheckConstraint(
            "action IN ('install', 'update', 'rollback', 'suspend', 'resume', 'revoke')",
            name="valid_action",
        ),
        Index("ix_catalog_installation_history", "installation_id", "sequence"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    installation_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_release_id: Mapped[UUID | None] = mapped_column(nullable=True)
    to_release_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogProposal(Base):
    """A non-developer contribution awaiting review before any Git commit exists."""

    __tablename__ = "proposal"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["resulting_artifact_version_id"],
            ["catalog.artifact_version.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_catalog_proposal_target_workspace", "target_workspace_id"),
        Index("ix_catalog_proposal_requested_by_status", "requested_by", "status"),
        Index("ix_catalog_proposal_artifact", "artifact_id"),
        CheckConstraint(
            "status IN ('submitted', 'in_review', 'approved', 'rejected', 'pull_request_open', "
            "'merged', 'closed_without_merge')",
            name="valid_status",
        ),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_workspace_id: Mapped[UUID] = mapped_column(nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    package: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    requested_by: Mapped[UUID] = mapped_column(nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    reviewer_id: Mapped[UUID | None] = mapped_column(nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    business_owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    technical_owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(700), nullable=True)
    merged_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resulting_artifact_version_id: Mapped[UUID | None] = mapped_column(nullable=True)


class CatalogScopePromotion(Base):
    """Widens an artifact's visibility scope; never duplicates the artifact."""

    __tablename__ = "scope_promotion"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id"], ["catalog.artifact.id"], ondelete="RESTRICT"),
        Index("ix_catalog_scope_promotion_artifact", "artifact_id", "requested_at"),
        CheckConstraint(
            "status IN ('awaiting-review', 'awaiting-approval', 'approved', 'rejected', 'applied')",
            name="valid_status",
        ),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    current_scope_unit_id: Mapped[UUID] = mapped_column(nullable=False)
    target_scope_unit_id: Mapped[UUID] = mapped_column(nullable=False)
    requested_by: Mapped[UUID] = mapped_column(nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    separation_of_duties: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approver_id: Mapped[UUID | None] = mapped_column(nullable=True)
    approval_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_by: Mapped[UUID | None] = mapped_column(nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogDistributionOperation(Base):
    __tablename__ = "distribution_operation"
    __table_args__ = (
        ForeignKeyConstraint(["installation_id"], ["catalog.installation.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["release_id"], ["catalog.release.id"], ondelete="RESTRICT"),
        UniqueConstraint("actor_id", "idempotency_key", name="uq_catalog_operation_actor_key"),
        CheckConstraint(
            "kind IN ('install', 'update', 'rollback', 'suspend', 'resume', 'revoke')",
            name="valid_kind",
        ),
        CheckConstraint(
            "status IN ('accepted', 'pending', 'running', 'succeeded', 'failed', 'rolled-back')",
            name="valid_status",
        ),
        Index("ix_catalog_operation_installation", "installation_id", "created_at"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    installation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    release_id: Mapped[UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "CatalogArtifact",
    "CatalogArtifactVersion",
    "CatalogAttestation",
    "CatalogCapabilityManifest",
    "CatalogDistributionOperation",
    "CatalogInstallation",
    "CatalogInstallationHistory",
    "CatalogPackageFile",
    "CatalogProposal",
    "CatalogPublicationRequest",
    "CatalogRelease",
    "CatalogScopePromotion",
]
