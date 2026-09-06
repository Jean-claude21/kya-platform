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


__all__ = [
    "CatalogArtifact",
    "CatalogArtifactVersion",
    "CatalogCapabilityManifest",
    "CatalogPackageFile",
]
