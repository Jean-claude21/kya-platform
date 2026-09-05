"""Persistent one-time platform-owner claim."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base


class PlatformBootstrapClaim(Base):
    __tablename__ = "platform_bootstrap_claim"
    __table_args__ = (
        CheckConstraint("state IN ('reserved', 'complete')", name="valid_state"),
        {"schema": "identity"},
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["PlatformBootstrapClaim"]
