"""Workspace membership, inheritance and deny precedence."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.organization import DateRange
from kya_platform.domain.workspaces import (
    AccessLevel,
    AccessSource,
    Workspace,
    WorkspaceAccess,
    WorkspaceKind,
    WorkspaceMembership,
    resolve_workspace_access,
)

ALICE = UUID("019914b2-1a40-7000-8000-000000000031")
CVSI = UUID("019914b2-1a40-7000-8000-000000000043")
PLATFORM = UUID("019914b2-1a40-7000-8000-000000000071")
NOW = datetime(2026, 9, 15, tzinfo=UTC)


def platform_workspace() -> Workspace:
    return Workspace(
        id=PLATFORM,
        key="platform",
        name="KYA Platform",
        kind=WorkspaceKind.TEAM,
        owner_unit_id=CVSI,
        linked_unit_ids=frozenset({CVSI}),
        validity=DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
    )


@pytest.mark.unit
def test_explicit_deny_wins_over_direct_and_inherited_access() -> None:
    membership = WorkspaceMembership(
        workspace_id=PLATFORM,
        principal_id=ALICE,
        level=AccessLevel.EDITOR,
        validity=DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
    )

    result = resolve_workspace_access(
        workspace=platform_workspace(),
        principal_id=ALICE,
        active_unit_id=CVSI,
        at=NOW,
        memberships=(membership,),
        inherited_levels=(AccessLevel.MANAGER,),
        denied_principal_ids=frozenset({ALICE}),
    )

    assert result == WorkspaceAccess.denied("explicit_deny")


@pytest.mark.unit
def test_expired_membership_grants_nothing_without_fallback() -> None:
    membership = WorkspaceMembership(
        workspace_id=PLATFORM,
        principal_id=ALICE,
        level=AccessLevel.EDITOR,
        validity=DateRange(
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 10, tzinfo=UTC),
        ),
    )

    result = resolve_workspace_access(
        workspace=platform_workspace(),
        principal_id=ALICE,
        active_unit_id=CVSI,
        at=NOW,
        memberships=(membership,),
    )

    assert result == WorkspaceAccess.denied("no_applicable_grant")


@pytest.mark.unit
def test_context_must_match_a_workspace_unit_for_inherited_access() -> None:
    other_unit = UUID("019914b2-1a40-7000-8000-000000000044")

    result = resolve_workspace_access(
        workspace=platform_workspace(),
        principal_id=ALICE,
        active_unit_id=other_unit,
        at=NOW,
        memberships=(),
        inherited_levels=(AccessLevel.MANAGER,),
    )

    assert result == WorkspaceAccess.denied("active_context_outside_workspace")


@pytest.mark.unit
def test_strongest_applicable_access_is_explained() -> None:
    result = resolve_workspace_access(
        workspace=platform_workspace(),
        principal_id=ALICE,
        active_unit_id=CVSI,
        at=NOW,
        memberships=(
            WorkspaceMembership(
                workspace_id=PLATFORM,
                principal_id=ALICE,
                level=AccessLevel.VIEWER,
                validity=DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
            ),
        ),
        inherited_levels=(AccessLevel.MANAGER,),
    )

    assert result.allowed
    assert result.level is AccessLevel.MANAGER
    assert result.source is AccessSource.INHERITED_UNIT
    assert result.reason_code == "inherited_unit_manager"


@pytest.mark.unit
def test_inactive_workspace_and_invalid_owner_link_are_rejected() -> None:
    with pytest.raises(ValueError, match="owner unit"):
        Workspace(
            id=PLATFORM,
            key="platform",
            name="KYA Platform",
            kind=WorkspaceKind.TEAM,
            owner_unit_id=CVSI,
            validity=DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
        )

    inactive = Workspace(
        id=PLATFORM,
        key="platform",
        name="KYA Platform",
        kind=WorkspaceKind.TEMPORARY,
        validity=DateRange(
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 10, tzinfo=UTC),
        ),
    )
    result = resolve_workspace_access(
        workspace=inactive,
        principal_id=ALICE,
        active_unit_id=CVSI,
        at=NOW,
        memberships=(),
    )
    assert result == WorkspaceAccess.denied("workspace_inactive")
