"""The MCP control-plane seed is deterministic and transactionally synchronized."""

from typing import Self

import pytest

from kya_platform.application.mcp_profiles import (
    SystemProfileRegistration,
    ToolRegistration,
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
