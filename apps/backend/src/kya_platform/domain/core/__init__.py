"""Canonical KYA master-data aggregates independent from delivery applications."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from kya_platform.domain.organization import DateRange

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


def _require_key(value: str, label: str) -> None:
    if _KEY.fullmatch(value) is None:
        raise ValueError(f"{label} must be a stable kebab-case identifier")


def _require_text(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} is required")


class RecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class PartyKind(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"


@dataclass(frozen=True, slots=True)
class Party:
    id: UUID
    kind: PartyKind
    display_name: str
    status: RecordStatus = RecordStatus.ACTIVE
    version: int = 1

    def __post_init__(self) -> None:
        _require_text(self.display_name, "party display name")
        if self.version < 1:
            raise ValueError("party version must be positive")


@dataclass(frozen=True, slots=True)
class PersonProfile:
    party_id: UUID
    given_name: str
    family_name: str
    preferred_name: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.given_name, "given name")
        _require_text(self.family_name, "family name")


class WorkRelationshipKind(StrEnum):
    EMPLOYEE = "employee"
    INTERN = "intern"
    CONTRACTOR = "contractor"
    CONSULTANT = "consultant"


@dataclass(frozen=True, slots=True)
class WorkRelationship:
    id: UUID
    person_id: UUID
    employer_unit_id: UUID
    kind: WorkRelationshipKind
    validity: DateRange
    personnel_number: str | None = None
    principal_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.personnel_number is not None:
            _require_text(self.personnel_number, "personnel number")


class ClientStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class ClientAccount:
    id: UUID
    key: str
    party_id: UUID
    owner_unit_id: UUID
    status: ClientStatus
    validity: DateRange
    version: int = 1

    def __post_init__(self) -> None:
        _require_key(self.key, "client key")
        if self.version < 1:
            raise ValueError("client version must be positive")


class ProjectStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    status: ProjectStatus
    validity: DateRange
    client_id: UUID | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _require_key(self.key, "project key")
        _require_text(self.name, "project name")
        if self.version < 1:
            raise ValueError("project version must be positive")


@dataclass(frozen=True, slots=True)
class Site:
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    owner_party_id: UUID
    country_code: str
    locality: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE
    version: int = 1

    def __post_init__(self) -> None:
        _require_key(self.key, "site key")
        _require_text(self.name, "site name")
        if _COUNTRY_CODE.fullmatch(self.country_code) is None:
            raise ValueError("country code must be ISO 3166-1 alpha-2 uppercase")
        if self.version < 1:
            raise ValueError("site version must be positive")


@dataclass(frozen=True, slots=True)
class ExternalReference:
    id: UUID
    system_key: str
    entity_type: str
    entity_id: UUID
    external_type: str
    external_id: str

    def __post_init__(self) -> None:
        _require_key(self.system_key, "system key")
        _require_key(self.entity_type, "entity type")
        _require_text(self.external_type, "external type")
        _require_text(self.external_id, "external id")


__all__ = [
    "ClientAccount",
    "ClientStatus",
    "ExternalReference",
    "Party",
    "PartyKind",
    "PersonProfile",
    "Project",
    "ProjectStatus",
    "RecordStatus",
    "Site",
    "WorkRelationship",
    "WorkRelationshipKind",
]
