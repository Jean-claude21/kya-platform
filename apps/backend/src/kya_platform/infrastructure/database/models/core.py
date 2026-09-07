"""Neon persistence for canonical KYA master data."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class CoreParty(Base):
    __tablename__ = "party"
    __table_args__ = (
        CheckConstraint("kind IN ('person', 'organization')", name="valid_kind"),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="valid_status"),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_core_party_display_name", "display_name"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CorePersonProfile(Base):
    __tablename__ = "person_profile"
    __table_args__ = ({"schema": "core"},)

    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), primary_key=True
    )
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)


class CoreOrganizationalUnitType(Base):
    __tablename__ = "organizational_unit_type"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="valid_status"),
        {"schema": "core"},
    )

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_parent_types: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class CoreOrganizationalUnit(Base):
    __tablename__ = "organizational_unit"
    __table_args__ = (
        UniqueConstraint("key", name="uq_core_organizational_unit_key"),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="valid_status"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_core_organizational_unit_type", "type_key"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    type_key: Mapped[str] = mapped_column(
        ForeignKey("core.organizational_unit_type.key", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CoreOrganizationalUnitRelation(Base):
    __tablename__ = "organizational_unit_relation"
    __table_args__ = (
        CheckConstraint("parent_unit_id <> child_unit_id", name="different_units"),
        CheckConstraint("kind IN ('hierarchical', 'transversal')", name="valid_kind"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        Index("ix_core_unit_relation_parent", "parent_unit_id", "kind"),
        Index("ix_core_unit_relation_child", "child_unit_id", "kind"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    parent_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    child_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoreWorkRelationship(Base):
    __tablename__ = "work_relationship"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('employee', 'intern', 'contractor', 'consultant')", name="valid_kind"
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        Index("ix_core_work_relationship_person", "person_id"),
        Index("ix_core_work_relationship_principal", "principal_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), nullable=False
    )
    employer_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    principal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    personnel_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)


class CorePosition(Base):
    __tablename__ = "position"
    __table_args__ = (
        UniqueConstraint("unit_id", "key", name="uq_core_position_unit_key"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)


class CorePositionAssignment(Base):
    __tablename__ = "position_assignment"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('primary', 'secondary', 'acting', 'delegation')", name="valid_kind"
        ),
        CheckConstraint(
            "allocation_percent IS NULL OR allocation_percent BETWEEN 1 AND 100",
            name="valid_allocation",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        Index("ix_core_position_assignment_person", "person_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), nullable=False
    )
    position_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.position.id", ondelete="RESTRICT"), nullable=False
    )
    scope_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    allocation_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reports_to_assignment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.position_assignment.id", ondelete="RESTRICT"), nullable=True
    )
    delegated_by_principal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)


class CoreClientAccount(Base):
    __tablename__ = "client_account"
    __table_args__ = (
        UniqueConstraint("key", name="uq_core_client_account_key"),
        CheckConstraint(
            "status IN ('prospect', 'active', 'suspended', 'inactive', 'archived')",
            name="valid_status",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_core_client_owner", "owner_unit_id", "status"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CoreContactPoint(Base):
    __tablename__ = "contact_point"
    __table_args__ = (
        UniqueConstraint(
            "party_id", "kind", "normalized_value", name="uq_core_contact_point_value"
        ),
        CheckConstraint("kind IN ('email', 'phone', 'address', 'url')", name="valid_kind"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        Index("ix_core_contact_point_party", "party_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="confidential")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)


class CoreProject(Base):
    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("key", name="uq_core_project_key"),
        CheckConstraint(
            "status IN ('planned', 'active', 'on_hold', 'completed', 'cancelled', 'archived')",
            name="valid_status",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="valid_business_period"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_core_project_owner", "owner_unit_id", "status"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.client_account.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CoreSite(Base):
    __tablename__ = "site"
    __table_args__ = (
        UniqueConstraint("key", name="uq_core_site_key"),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name="valid_status"),
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="valid_country_code"),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_core_site_owner", "owner_unit_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organizational_unit.id", ondelete="RESTRICT"), nullable=False
    )
    owner_party_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.party.id", ondelete="RESTRICT"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    locality: Mapped[str | None] = mapped_column(String(240), nullable=True)
    address: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoreProjectSite(Base):
    __tablename__ = "project_site"
    __table_args__ = ({"schema": "core"},)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.project.id", ondelete="RESTRICT"), primary_key=True
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.site.id", ondelete="RESTRICT"), primary_key=True
    )
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoreExternalReference(Base):
    __tablename__ = "external_reference"
    __table_args__ = (
        UniqueConstraint(
            "system_key",
            "entity_type",
            "external_type",
            "external_id",
            name="uq_core_external_reference",
        ),
        Index("ix_core_external_reference_entity", "entity_type", "entity_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    system_key: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    external_type: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "CoreClientAccount",
    "CoreContactPoint",
    "CoreExternalReference",
    "CoreOrganizationalUnit",
    "CoreOrganizationalUnitRelation",
    "CoreOrganizationalUnitType",
    "CoreParty",
    "CorePersonProfile",
    "CorePosition",
    "CorePositionAssignment",
    "CoreProject",
    "CoreProjectSite",
    "CoreSite",
    "CoreWorkRelationship",
]
