"""Persistence model for governed intelligence watchlists."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class IntelligenceWatchRow(Base):
    __tablename__ = "watch"
    __table_args__ = (
        UniqueConstraint("owner_unit_id", "key", name="uq_intelligence_watch_unit_key"),
        CheckConstraint("status IN ('active','paused')", name="valid_status"),
        CheckConstraint("revision > 0", name="positive_revision"),
        Index("ix_intelligence_watch_unit_status", "owner_unit_id", "status"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    asset_keys: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IntelligenceSignalRow(Base):
    __tablename__ = "signal"
    __table_args__ = (
        UniqueConstraint("watch_id", "chunk_id", name="uq_intelligence_signal_watch_chunk"),
        CheckConstraint("status IN ('open','acknowledged')", name="valid_status"),
        CheckConstraint("revision > 0", name="positive_revision"),
        Index("ix_intelligence_signal_watch_status", "watch_id", "status", "observed_at"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    watch_id: Mapped[UUID] = mapped_column(
        ForeignKey("intelligence.watch.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.content_chunk.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("data.snapshot.id", ondelete="RESTRICT"), nullable=False
    )
    citation_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1200), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    page_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    acknowledged_by: Mapped[UUID | None] = mapped_column()
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["IntelligenceSignalRow", "IntelligenceWatchRow"]
