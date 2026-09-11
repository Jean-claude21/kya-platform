"""Neon persistence for secret governance metadata; values never live here."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base


class SecretReferenceRow(Base):
    __tablename__ = "secret_reference"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('personal', 'team', 'service', 'application', 'environment')",
            name="ck_secret_reference_valid_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'rotation_due', 'revoked')",
            name="ck_secret_reference_valid_status",
        ),
        CheckConstraint(
            "environment IN ('local', 'preview', 'test', 'production')",
            name="ck_secret_reference_valid_environment",
        ),
        Index("ix_secret_reference_owner_scope", "owner_scope"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    locator: Mapped[str] = mapped_column(String(512), nullable=False)
    key_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["SecretReferenceRow"]
