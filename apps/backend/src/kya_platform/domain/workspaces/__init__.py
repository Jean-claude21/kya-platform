"""Workspace boundaries and explainable access resolution."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
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


class AccessLevel(StrEnum):
    VIEWER = "viewer"
    GUEST = "guest"
    MEMBER = "member"
    CONTRIBUTOR = "contributor"
    EDITOR = "editor"
    MANAGER = "manager"
    OWNER = "owner"


_ACCESS_RANK = {
    AccessLevel.VIEWER: 10,
    AccessLevel.GUEST: 20,
    AccessLevel.MEMBER: 30,
    AccessLevel.CONTRIBUTOR: 40,
    AccessLevel.EDITOR: 50,
    AccessLevel.MANAGER: 60,
    AccessLevel.OWNER: 70,
}


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


class WorkspaceQueryPort(Protocol):
    async def get(self, workspace_key: str) -> Workspace | None:
        """Load one workspace after an access decision."""

    async def list_by_keys(self, workspace_keys: Sequence[str]) -> Sequence[Workspace]:
        """Load only keys already filtered by the authorization provider."""

    async def list_memberships(self, workspace_id: UUID) -> Sequence[WorkspaceMembership]:
        """List dated memberships for a workspace whose access was already checked."""


class WorkspaceCommandPort(Protocol):
    async def add_membership(
        self, membership: WorkspaceMembership, *, actor_id: UUID
    ) -> WorkspaceMembership:
        """Persist a validated membership and enqueue its policy projection."""


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

    level, source = max(candidates, key=lambda candidate: _ACCESS_RANK[candidate[0]])
    return WorkspaceAccess(True, level, source, f"{source.value}_{level.name.lower()}")


__all__ = [
    "AccessLevel",
    "AccessSource",
    "Workspace",
    "WorkspaceAccess",
    "WorkspaceCommandPort",
    "WorkspaceKind",
    "WorkspaceMembership",
    "WorkspaceQueryPort",
    "resolve_workspace_access",
]
