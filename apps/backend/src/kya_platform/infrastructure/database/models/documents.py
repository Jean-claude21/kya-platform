"""Native document runtime persistence mappings."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class DocumentDefinitionRow(Base):
    __tablename__ = "definition"
    __table_args__ = (
        UniqueConstraint("public_id", "version", name="uq_document_definition_public_version"),
        UniqueConstraint("release_id", name="uq_document_definition_release"),
        UniqueConstraint("digest", name="uq_document_definition_digest"),
        Index("ix_document_definition_scope", "owner_scope", "public_id"),
        {"schema": "documents"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog.release.id", ondelete="RESTRICT"), nullable=False
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[UUID] = mapped_column(nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentRecordRow(Base):
    __tablename__ = "record"
    __table_args__ = (
        CheckConstraint("current_revision > 0", name="positive_revision"),
        Index("ix_document_record_scope_state", "owner_scope", "state", "updated_at"),
        Index("ix_document_record_definition", "definition_id", "created_at"),
        {"schema": "documents"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.definition.id", ondelete="RESTRICT"), nullable=False
    )
    owner_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentRevisionRow(Base):
    __tablename__ = "revision"
    __table_args__ = (
        CheckConstraint("revision > 0", name="positive_revision"),
        UniqueConstraint("record_id", "digest", name="uq_document_revision_record_digest"),
        {"schema": "documents"},
    )

    record_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.record.id", ondelete="RESTRICT"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authored_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentEvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("revision > 0", name="positive_revision"),
        CheckConstraint(
            "kind IN ('transition','signature','attachment','notification')",
            name="valid_kind",
        ),
        UniqueConstraint("record_id", "digest", name="uq_document_evidence_record_digest"),
        Index("ix_document_evidence_record_time", "record_id", "occurred_at"),
        {"schema": "documents"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    record_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.record.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "DocumentDefinitionRow",
    "DocumentEvidenceRow",
    "DocumentRecordRow",
    "DocumentRevisionRow",
]
