"""Persistence models that make sensitive operations traceable and retry-safe."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class AuditEvent(Base):
    """Append-only evidence; mutation is also blocked by a database trigger."""

    __tablename__ = "event"
    __table_args__ = (
        Index("ix_audit_event_target", "target_type", "target_id"),
        Index("ix_audit_event_correlation", "correlation_id"),
        {"schema": "audit"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class OutboxEvent(Base):
    """Transactional message awaiting an idempotent external projection."""

    __tablename__ = "outbox_event"
    __table_args__ = (
        Index("ix_reliability_outbox_pending", "processed_at", "available_at"),
        {"schema": "reliability"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IdempotencyRecord(Base):
    """Stored deterministic result for a caller-scoped command key."""

    __tablename__ = "idempotency_record"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key"),
        {"schema": "reliability"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["AuditEvent", "IdempotencyRecord", "OutboxEvent"]
