"""Persistent MCP tool catalog, profiles, assignments and restrictive preferences."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class McpToolDefinition(Base):
    __tablename__ = "tool_definition"
    __table_args__ = (
        UniqueConstraint("key", name="uq_mcp_tool_definition_key"),
        UniqueConstraint("handler_key", name="uq_mcp_tool_definition_handler"),
        CheckConstraint(
            "risk IN ('read', 'controlled-write', 'sensitive-write')",
            name="valid_risk",
        ),
        CheckConstraint(
            "lifecycle_state IN ('draft', 'active', 'retired')",
            name="valid_lifecycle_state",
        ),
        {"schema": "mcp_control"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    namespace: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    target_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_relation: Mapped[str] = mapped_column(String(80), nullable=False)
    risk: Mapped[str] = mapped_column(String(32), nullable=False)
    is_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_idempotency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handler_key: Mapped[str] = mapped_column(String(160), nullable=False)
    input_schema_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_schema_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class McpToolProfile(Base):
    __tablename__ = "tool_profile"
    __table_args__ = (
        UniqueConstraint("key", name="uq_mcp_tool_profile_key"),
        CheckConstraint(
            "kind IN ('system', 'business', 'personal-template')",
            name="valid_kind",
        ),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="valid_status"),
        CheckConstraint("version > 0 AND revision > 0", name="positive_versions"),
        CheckConstraint(
            "max_active_tools > 0 AND max_active_tools <= 24",
            name="valid_max_active_tools",
        ),
        {"schema": "mcp_control"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_unit_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_active_tools: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class McpToolProfileItem(Base):
    __tablename__ = "tool_profile_item"
    __table_args__ = (
        ForeignKeyConstraint(["profile_id"], ["mcp_control.tool_profile.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tool_id"], ["mcp_control.tool_definition.id"], ondelete="RESTRICT"),
        CheckConstraint("state IN ('enabled', 'disabled')", name="valid_state"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        {"schema": "mcp_control"},
    )

    profile_id: Mapped[UUID] = mapped_column(primary_key=True)
    tool_id: Mapped[UUID] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    configured_by: Mapped[UUID] = mapped_column(nullable=False)
    configured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class McpToolProfileAssignment(Base):
    __tablename__ = "tool_profile_assignment"
    __table_args__ = (
        ForeignKeyConstraint(["profile_id"], ["mcp_control.tool_profile.id"], ondelete="CASCADE"),
        CheckConstraint(
            "subject_type IN ('user', 'team', 'role', 'org_unit')",
            name="valid_subject_type",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="valid_validity_window",
        ),
        Index(
            "ix_mcp_profile_assignment_subject",
            "subject_type",
            "subject_key",
            "context_unit_key",
            "valid_from",
            "valid_until",
        ),
        {"schema": "mcp_control"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    subject_type: Mapped[str] = mapped_column(String(24), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(512), nullable=False)
    context_unit_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by: Mapped[UUID] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class McpUserToolPreference(Base):
    __tablename__ = "user_tool_preference"
    __table_args__ = (
        ForeignKeyConstraint(["tool_id"], ["mcp_control.tool_definition.id"], ondelete="CASCADE"),
        CheckConstraint("state = 'disabled'", name="restrictive_state_only"),
        CheckConstraint("revision > 0", name="positive_revision"),
        Index("ix_mcp_user_preference_context", "principal_id", "active_unit_key"),
        {"schema": "mcp_control"},
    )

    principal_id: Mapped[UUID] = mapped_column(primary_key=True)
    active_unit_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(128), primary_key=True, default="")
    tool_id: Mapped[UUID] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[UUID] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


__all__ = [
    "McpToolDefinition",
    "McpToolProfile",
    "McpToolProfileAssignment",
    "McpToolProfileItem",
    "McpUserToolPreference",
]
