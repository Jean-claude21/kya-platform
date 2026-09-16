"""Registered systems, capabilities and temporal data authority."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from kya_platform.contracts.artifact_manifest import RiskLevel
from kya_platform.domain.organization import DateRange

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class SystemStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RETIRED = "retired"


class AvailabilityLevel(StrEnum):
    UNKNOWN = "unknown"
    BEST_EFFORT = "best-effort"
    BUSINESS_HOURS = "business-hours"
    CONTINUOUS = "continuous"


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class InterfaceKind(StrEnum):
    REST_API = "rest-api"
    WEBHOOK = "webhook"
    EVENT_STREAM = "event-stream"
    FILE_EXCHANGE = "file-exchange"
    MCP = "mcp"


@dataclass(frozen=True, slots=True)
class ApprovedInterface:
    name: str
    kind: InterfaceKind
    contract_uri: str
    approved: bool

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.contract_uri.strip():
            raise ValueError("interface name and contract reference are required")


@dataclass(frozen=True, slots=True)
class RegisteredSystem:
    id: UUID
    key: str
    name: str
    business_owner: str
    technical_owner: str
    status: SystemStatus
    environments: frozenset[str]
    interfaces: tuple[ApprovedInterface, ...]
    availability: AvailabilityLevel = AvailabilityLevel.UNKNOWN

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("system key must be a stable kebab-case identifier")
        if not all(
            value.strip() for value in (self.name, self.business_owner, self.technical_owner)
        ):
            raise ValueError("system name and owners are required")
        if not self.environments:
            raise ValueError("a registered system must declare an environment")


@dataclass(frozen=True, slots=True)
class SystemCapability:
    key: str
    name: str
    provider_system_id: UUID
    contract_uri: str
    risk: RiskLevel

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("capability key must be a stable kebab-case identifier")
        if not self.name.strip() or not self.contract_uri.strip():
            raise ValueError("capability name and contract reference are required")


@dataclass(frozen=True, slots=True)
class DataCategory:
    key: str
    name: str
    sensitivity: DataSensitivity

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None or not self.name.strip():
            raise ValueError("data category requires a stable key and name")


@dataclass(frozen=True, slots=True)
class DataAuthority:
    id: UUID
    category_key: str
    system_id: UUID
    scope: str
    validity: DateRange
    exclusive: bool = True

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.category_key) is None or not self.scope.strip():
            raise ValueError("authority category and scope are required")

    def overlaps(self, other: DataAuthority) -> bool:
        if self.category_key != other.category_key or self.scope != other.scope:
            return False
        self_end = self.validity.valid_until
        other_end = other.validity.valid_until
        return (self_end is None or other.validity.valid_from < self_end) and (
            other_end is None or self.validity.valid_from < other_end
        )


class AuthorityConflictError(ValueError):
    """Two exclusive sources claim the same data, scope and period."""


class AuthorityNotFoundError(LookupError):
    """No explicit source of truth exists for the requested instant."""


@dataclass(frozen=True, slots=True)
class SystemRegistry:
    systems: tuple[RegisteredSystem, ...]
    capabilities: tuple[SystemCapability, ...] = ()
    authorities: tuple[DataAuthority, ...] = ()

    def __post_init__(self) -> None:
        system_ids = [system.id for system in self.systems]
        if len(system_ids) != len(set(system_ids)):
            raise ValueError("registered system identifiers must be unique")
        known = set(system_ids)
        if any(capability.provider_system_id not in known for capability in self.capabilities):
            raise ValueError("capability provider must be a registered system")
        if any(authority.system_id not in known for authority in self.authorities):
            raise ValueError("data authority must reference a registered system")
        for index, authority in enumerate(self.authorities):
            for other in self.authorities[index + 1 :]:
                if (
                    authority.system_id != other.system_id
                    and authority.exclusive
                    and other.exclusive
                    and authority.overlaps(other)
                ):
                    raise AuthorityConflictError(
                        "exclusive data authorities overlap for category and scope"
                    )

    def authority_for(self, category_key: str, scope: str, *, at: datetime) -> RegisteredSystem:
        matches = [
            authority
            for authority in self.authorities
            if authority.category_key == category_key
            and authority.scope == scope
            and authority.exclusive
            and authority.validity.contains(at)
        ]
        if len(matches) != 1:
            if len(matches) > 1:
                raise AuthorityConflictError("multiple active authorities found")
            raise AuthorityNotFoundError("no active authority found")
        return next(system for system in self.systems if system.id == matches[0].system_id)


class SystemQueryPort(Protocol):
    async def get(self, system_key: str) -> RegisteredSystem | None: ...

    async def list_by_keys(self, system_keys: tuple[str, ...]) -> tuple[RegisteredSystem, ...]: ...

    async def resolve_authority(
        self, category_key: str, scope: str, at: datetime
    ) -> tuple[DataAuthority, RegisteredSystem] | None: ...


__all__ = [
    "ApprovedInterface",
    "AuthorityConflictError",
    "AuthorityNotFoundError",
    "AvailabilityLevel",
    "DataAuthority",
    "DataCategory",
    "DataSensitivity",
    "InterfaceKind",
    "RegisteredSystem",
    "SystemCapability",
    "SystemQueryPort",
    "SystemRegistry",
    "SystemStatus",
]
