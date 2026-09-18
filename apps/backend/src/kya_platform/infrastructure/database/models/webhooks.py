"""Persistent webhook routing metadata without signing-secret values."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base


class WebhookSubscriptionRow(Base):
    __tablename__ = "webhook_subscription"
    __table_args__ = (
        Index("ix_webhook_subscription_scope_enabled", "owner_scope", "is_enabled"),
        {"schema": "reliability"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    secret_reference_id: Mapped[UUID] = mapped_column(nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["WebhookSubscriptionRow"]
