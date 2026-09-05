"""Persistent binding between external authentication and KYA principals."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class ExternalIdentity(Base):
    """An issuer/subject pair that can never be rebound to another principal."""

    __tablename__ = "external_identity"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_external_identity_subject"),
        Index("ix_external_identity_principal", "principal_id"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["ExternalIdentity"]
