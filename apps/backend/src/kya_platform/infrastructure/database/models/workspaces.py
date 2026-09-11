"""Neon persistence for workspace boundaries and dated memberships."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class WorkspaceRow(Base):
    __tablename__ = "workspace"
    __table_args__ = (
        UniqueConstraint("key", name="uq_workspace_key"),
        CheckConstraint(
            "kind IN ('personal', 'team', 'direction', 'project', 'country', 'group', "
            "'temporary', 'restricted')",
            name="ck_workspace_valid_kind",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="ck_workspace_valid_period"
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    owner_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkspaceLinkedUnitRow(Base):
    """A workspace is visible through an organizational unit's active context."""

    __tablename__ = "workspace_linked_unit"
    __table_args__ = ({"schema": "core"},)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.workspace.id", ondelete="CASCADE"), primary_key=True
    )
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="CASCADE"), primary_key=True
    )


class WorkspaceMembershipRow(Base):
    __tablename__ = "workspace_membership"
    __table_args__ = (
        CheckConstraint(
            "level IN ('viewer', 'guest', 'member', 'contributor', 'editor', 'manager', "
            "'owner')",
            name="ck_workspace_membership_valid_level",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_workspace_membership_valid_period",
        ),
        Index("ix_workspace_membership_principal", "principal_id"),
        Index("ix_workspace_membership_workspace", "workspace_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.workspace.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delegated_by: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["WorkspaceLinkedUnitRow", "WorkspaceMembershipRow", "WorkspaceRow"]

