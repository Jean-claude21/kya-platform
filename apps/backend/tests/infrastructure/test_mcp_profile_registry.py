"""The MCP control-plane seed is deterministic and transactionally synchronized."""

from types import SimpleNamespace
from typing import Self
from uuid import UUID

import pytest

from kya_platform.application.mcp_profiles import (
    McpProfileConflictError,
    McpProfileReferenceError,
    SystemProfileRegistration,
    ToolRegistration,
    UserToolPreferenceKey,
)
from kya_platform.infrastructure.database.mcp_profiles import SqlAlchemyMcpProfileRegistry


class Session:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: object) -> None:
        self.statements.append(statement)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def begin(self) -> Session:
        return self.session


class MutationSession:
    def __init__(self, scalars: list[object | None], *, rowcount: int = 1) -> None:
        self.scalar_results = scalars
        self.rowcount = rowcount
        self.added: list[object] = []
        self.statements: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> Self:
        return self

    async def scalar(self, statement: object) -> object | None:
        self.statements.append(statement)
        return self.scalar_results.pop(0)

    async def scalars(self, statement: object) -> tuple[str, ...]:
        self.statements.append(statement)
        return ("data.find", "data.read")

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return SimpleNamespace(rowcount=self.rowcount)

    def add(self, row: object) -> None:
        self.added.append(row)


class MutationSessions:
    def __init__(self, session: MutationSession) -> None:
        self.session = session

    def __call__(self) -> MutationSession:
        return self.session


def tool(key: str) -> ToolRegistration:
    return ToolRegistration(
        key,
        "data",
        key,
        f"Outil {key}",
        "data:read",
        "org_unit",
        "can_view",
        "read",
        False,
        False,
        False,
    )


@pytest.mark.asyncio
async def test_synchronizes_exact_system_profile_membership_with_stable_ids() -> None:
    session = Session()
    repository = SqlAlchemyMcpProfileRegistry(Sessions(session))  # type: ignore[arg-type]
    tools = (tool("find"), tool("read"))
    profiles = (
        SystemProfileRegistration("data-reader", "Lecteur", "Lecture", ("find", "read")),
    )

    await repository.synchronize(tools, profiles)

    assert len(session.statements) == 6
    parameters = [statement.compile().params for statement in session.statements]
    assert parameters[0]["key"] == "find"
    assert parameters[1]["key"] == "read"
    assert parameters[2]["key"] == "data-reader"
    assert parameters[4]["sort_order"] == 0
    assert parameters[5]["sort_order"] == 1
    assert parameters[4]["profile_id"] == parameters[5]["profile_id"]


@pytest.mark.asyncio
async def test_empty_registry_is_a_no_op() -> None:
    session = Session()
    repository = SqlAlchemyMcpProfileRegistry(Sessions(session))  # type: ignore[arg-type]
    await repository.synchronize((), ())
    assert session.statements == []


PREFERENCE = UserToolPreferenceKey(
    UUID(int=10), "kya/togo/cvsi", "claude", "data.find"
)


@pytest.mark.asyncio
async def test_lists_global_and_client_specific_disabled_tools() -> None:
    session = MutationSession([])
    repository = SqlAlchemyMcpProfileRegistry(MutationSessions(session))  # type: ignore[arg-type]
    disabled = await repository.list_disabled_tools(
        principal_id=PREFERENCE.principal_id,
        active_unit_key=PREFERENCE.active_unit_key,
        client_id=PREFERENCE.client_id,
    )
    assert disabled == frozenset({"data.find", "data.read"})


@pytest.mark.asyncio
async def test_disables_new_preference_at_revision_one() -> None:
    session = MutationSession([UUID(int=20), None])
    repository = SqlAlchemyMcpProfileRegistry(MutationSessions(session))  # type: ignore[arg-type]
    revision = await repository.disable_tool(
        PREFERENCE, actor_id=PREFERENCE.principal_id, expected_revision=0
    )
    assert revision == 1
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_updates_preference_only_from_current_revision() -> None:
    row = SimpleNamespace(revision=2, updated_by=UUID(int=0))
    session = MutationSession([UUID(int=20), row])
    repository = SqlAlchemyMcpProfileRegistry(MutationSessions(session))  # type: ignore[arg-type]
    revision = await repository.disable_tool(
        PREFERENCE, actor_id=PREFERENCE.principal_id, expected_revision=2
    )
    assert revision == 3
    assert row.updated_by == PREFERENCE.principal_id


@pytest.mark.asyncio
async def test_rejects_unknown_tool_and_stale_preference_revision() -> None:
    missing = SqlAlchemyMcpProfileRegistry(  # type: ignore[arg-type]
        MutationSessions(MutationSession([None]))
    )
    with pytest.raises(McpProfileReferenceError):
        await missing.disable_tool(PREFERENCE, actor_id=UUID(int=10), expected_revision=0)
    stale = SqlAlchemyMcpProfileRegistry(  # type: ignore[arg-type]
        MutationSessions(MutationSession([UUID(int=20), SimpleNamespace(revision=2)]))
    )
    with pytest.raises(McpProfileConflictError):
        await stale.disable_tool(PREFERENCE, actor_id=UUID(int=10), expected_revision=1)


@pytest.mark.asyncio
async def test_inherits_only_the_expected_preference_revision() -> None:
    session = MutationSession([UUID(int=20)])
    repository = SqlAlchemyMcpProfileRegistry(MutationSessions(session))  # type: ignore[arg-type]
    await repository.inherit_tool(PREFERENCE, expected_revision=3)
    stale = SqlAlchemyMcpProfileRegistry(  # type: ignore[arg-type]
        MutationSessions(MutationSession([UUID(int=20)], rowcount=0))
    )
    with pytest.raises(McpProfileConflictError):
        await stale.inherit_tool(PREFERENCE, expected_revision=3)
    missing = SqlAlchemyMcpProfileRegistry(  # type: ignore[arg-type]
        MutationSessions(MutationSession([None]))
    )
    with pytest.raises(McpProfileReferenceError):
        await missing.inherit_tool(PREFERENCE, expected_revision=3)
