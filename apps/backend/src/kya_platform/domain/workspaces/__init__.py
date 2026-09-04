"""Workspace boundaries and explainable access resolution."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from uuid import UUID

from kya_platform.domain.organization import DateRange

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class WorkspaceKind(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"
    DIRECTION = "direction"
    PROJECT = "project"
    COUNTRY = "country"
    GROUP = "group"
    TEMPORARY = "temporary"
    RESTRICTED = "restricted"


class AccessLevel(IntEnum):
    VIEWER = 10
    GUEST = 20
    MEMBER = 30
    CONTRIBUTOR = 40
    EDITOR = 50
    MANAGER = 60
    OWNER = 70


class AccessSource(StrEnum):
    DIRECT_MEMBERSHIP = "direct_membership"
    INHERITED_UNIT = "inherited_unit"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    key: str
    name: str
    kind: WorkspaceKind
    validity: DateRange
    owner_unit_id: UUID | None = None
    linked_unit_ids: frozenset[UUID] = field(default_factory=frozenset)
    classification: str = "internal"

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("workspace key must be a stable kebab-case identifier")
        if not self.name.strip():
            raise ValueError("workspace name is required")
        if self.owner_unit_id is not None and self.owner_unit_id not in self.linked_unit_ids:
            raise ValueError("owner unit must also be linked to the workspace")


@dataclass(frozen=True, slots=True)
class WorkspaceMembership:
    workspace_id: UUID
    principal_id: UUID
    level: AccessLevel
    validity: DateRange
    delegated_by: UUID | None = None

    def is_active(self, instant: datetime) -> bool:
        return self.validity.contains(instant)


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    allowed: bool
    level: AccessLevel | None
    source: AccessSource | None
    reason_code: str

    @classmethod
    def denied(cls, reason_code: str) -> WorkspaceAccess:
        return cls(False, None, None, reason_code)


def resolve_workspace_access(
    *,
    workspace: Workspace,
    principal_id: UUID,
    active_unit_id: UUID,
    at: datetime,
    memberships: tuple[WorkspaceMembership, ...],
    inherited_levels: tuple[AccessLevel, ...] = (),
    denied_principal_ids: frozenset[UUID] = frozenset(),
) -> WorkspaceAccess:
    """Resolve local facts; the external policy engine remains authoritative at runtime."""

    if not workspace.validity.contains(at):
        return WorkspaceAccess.denied("workspace_inactive")
    if principal_id in denied_principal_ids:
        return WorkspaceAccess.denied("explicit_deny")

    candidates: list[tuple[AccessLevel, AccessSource]] = [
        (membership.level, AccessSource.DIRECT_MEMBERSHIP)
        for membership in memberships
        if membership.workspace_id == workspace.id
        and membership.principal_id == principal_id
        and membership.is_active(at)
    ]

    if inherited_levels:
        if active_unit_id not in workspace.linked_unit_ids:
            return WorkspaceAccess.denied("active_context_outside_workspace")
        candidates.extend((level, AccessSource.INHERITED_UNIT) for level in inherited_levels)

    if not candidates:
        return WorkspaceAccess.denied("no_applicable_grant")

    level, source = max(candidates, key=lambda candidate: candidate[0])
    return WorkspaceAccess(True, level, source, f"{source.value}_{level.name.lower()}")


__all__ = [
    "AccessLevel",
    "AccessSource",
    "Workspace",
    "WorkspaceAccess",
    "WorkspaceKind",
    "WorkspaceMembership",
    "resolve_workspace_access",
]
