"""Workspace persistence resolves boundaries and dated memberships from Neon."""

from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.domain.organization import DateRange
from kya_platform.domain.workspaces import AccessLevel, WorkspaceKind, WorkspaceMembership
from kya_platform.infrastructure.database.models import (
    WorkspaceMembershipRow,
    WorkspaceRow,
)
from kya_platform.infrastructure.database.workspaces import SqlAlchemyWorkspaceRepository

PLATFORM = UUID("019a0000-0000-7000-8000-000000000001")
CVSI = UUID("019a0000-0000-7000-8000-000000000002")
ALICE = UUID("019a0000-0000-7000-8000-000000000003")
VALID_FROM = datetime(2026, 9, 1, tzinfo=UTC)


def platform_row() -> WorkspaceRow:
    return WorkspaceRow(
        id=PLATFORM,
        key="platform",
        name="KYA Platform",
        kind="team",
        classification="internal",
        owner_unit_id=CVSI,
        valid_from=VALID_FROM,
        valid_until=None,
        created_by=CVSI,
    )


class ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def __iter__(self) -> object:
        return iter(self.values)


class ExecuteResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def __iter__(self) -> object:
        return iter(self.rows)


class Session:
    def __init__(
        self,
        *,
        scalar_values: list[object] | None = None,
        scalars_values: list[list[object]] | None = None,
        execute_values: list[list[tuple[object, ...]]] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalars_values = scalars_values or []
        self.execute_values = execute_values or []
        self.added: list[object] = []
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, statement: object) -> object:
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> ScalarsResult:
        return ScalarsResult(self.scalars_values.pop(0))

    async def execute(self, statement: object) -> ExecuteResult:
        return ExecuteResult(self.execute_values.pop(0))

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_get_returns_none_for_an_unknown_key() -> None:
    session = Session(scalar_values=[None])
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.get("unknown")

    assert result is None


@pytest.mark.asyncio
async def test_get_resolves_linked_units_alongside_the_workspace() -> None:
    session = Session(scalar_values=[platform_row()], scalars_values=[[CVSI]])
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.get("platform")

    assert result is not None
    assert result.key == "platform"
    assert result.kind == WorkspaceKind.TEAM
    assert result.linked_unit_ids == frozenset({CVSI})
    assert result.owner_unit_id == CVSI


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_an_unknown_identifier() -> None:
    session = Session(scalar_values=[None])
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.get_by_id(PLATFORM)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_resolves_linked_units_alongside_the_workspace() -> None:
    session = Session(scalar_values=[platform_row()], scalars_values=[[CVSI]])
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.get_by_id(PLATFORM)

    assert result is not None
    assert result.id == PLATFORM
    assert result.linked_unit_ids == frozenset({CVSI})


@pytest.mark.asyncio
async def test_list_by_keys_returns_empty_without_querying_for_an_empty_request() -> None:
    session = Session()
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.list_by_keys(())

    assert result == ()


@pytest.mark.asyncio
async def test_list_by_keys_preserves_the_authorized_key_order() -> None:
    other = WorkspaceRow(
        id=UUID("019a0000-0000-7000-8000-000000000004"),
        key="restricted",
        name="Direction générale",
        kind="restricted",
        classification="internal",
        owner_unit_id=None,
        valid_from=VALID_FROM,
        valid_until=None,
        created_by=CVSI,
    )
    session = Session(
        scalars_values=[[other, platform_row()]],
        execute_values=[[(PLATFORM, CVSI)]],
    )
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.list_by_keys(("platform", "restricted"))

    assert [item.key for item in result] == ["platform", "restricted"]
    assert result[0].linked_unit_ids == frozenset({CVSI})
    assert result[1].linked_unit_ids == frozenset()


@pytest.mark.asyncio
async def test_list_memberships_maps_persisted_rows_to_the_domain_type() -> None:
    row = WorkspaceMembershipRow(
        id=UUID("019a0000-0000-7000-8000-000000000005"),
        workspace_id=PLATFORM,
        principal_id=ALICE,
        level="viewer",
        valid_from=VALID_FROM,
        valid_until=None,
        delegated_by=None,
    )
    session = Session(scalars_values=[[row]])
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))

    result = await repository.list_memberships(PLATFORM)

    assert result == (
        WorkspaceMembership(
            workspace_id=PLATFORM,
            principal_id=ALICE,
            level=AccessLevel.VIEWER,
            validity=DateRange(VALID_FROM, None),
            delegated_by=None,
        ),
    )


@pytest.mark.asyncio
async def test_add_membership_persists_and_commits_a_new_row() -> None:
    session = Session()
    repository = SqlAlchemyWorkspaceRepository(Sessions(session))
    membership = WorkspaceMembership(
        workspace_id=PLATFORM,
        principal_id=ALICE,
        level=AccessLevel.VIEWER,
        validity=DateRange(VALID_FROM, None),
        delegated_by=None,
    )

    result = await repository.add_membership(membership, actor_id=CVSI)

    assert result == membership
    assert session.committed is True
    assert len(session.added) == 1
    added = session.added[0]
    assert isinstance(added, WorkspaceMembershipRow)
    assert added.workspace_id == PLATFORM
    assert added.principal_id == ALICE
    assert added.level == "viewer"
