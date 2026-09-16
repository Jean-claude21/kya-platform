"""MCP system profile synchronization validates every bounded reference."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from kya_platform.application.mcp_profiles import (
    McpPreferenceCommand,
    McpPreferenceService,
    McpProfileService,
    SystemProfileRegistration,
    ToolRegistration,
    UserToolPreferenceKey,
)


class Registry:
    def __init__(self) -> None:
        self.calls: list[
            tuple[tuple[ToolRegistration, ...], tuple[SystemProfileRegistration, ...]]
        ] = []

    async def synchronize(
        self,
        tools: tuple[ToolRegistration, ...],
        profiles: tuple[SystemProfileRegistration, ...],
    ) -> None:
        self.calls.append((tools, profiles))


def registration(key: str) -> ToolRegistration:
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
async def test_synchronizes_known_bounded_tools() -> None:
    registry = Registry()
    tools = (registration("find"), registration("read"))
    profiles = (SystemProfileRegistration("reader", "Lecteur", "Lecture", ("find", "read")),)
    await McpProfileService(registry).synchronize(tools, profiles)
    assert registry.calls == [(tools, profiles)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tools", "profile", "message"),
    [
        ((registration("find"), registration("find")), None, "unique"),
        (
            (registration("find"),),
            SystemProfileRegistration("empty", "Vide", "Vide", ()),
            "unknown",
        ),
        (
            (registration("find"),),
            SystemProfileRegistration("bad", "Invalide", "Invalide", ("missing",)),
            "unknown",
        ),
    ],
)
async def test_rejects_invalid_registry(
    tools: tuple[ToolRegistration, ...],
    profile: SystemProfileRegistration | None,
    message: str,
) -> None:
    profiles = () if profile is None else (profile,)
    with pytest.raises(ValueError, match=message):
        await McpProfileService(Registry()).synchronize(tools, profiles)


@pytest.mark.asyncio
async def test_rejects_profiles_over_the_limit() -> None:
    tools = tuple(registration(f"tool-{index}") for index in range(25))
    profile = SystemProfileRegistration(
        "oversized", "Trop grand", "Trop grand", tuple(item.key for item in tools)
    )
    with pytest.raises(ValueError, match="24-tool"):
        await McpProfileService(Registry()).synchronize(tools, (profile,))


class Preferences:
    async def list_disabled_tools(self, **kwargs: object) -> frozenset[str]:
        return frozenset()

    async def disable_tool(self, key: object, **kwargs: object) -> int:
        return 1

    async def inherit_tool(self, key: object, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_preference_service_only_accepts_valid_optimistic_revisions() -> None:
    service = McpPreferenceService(Preferences())  # type: ignore[arg-type]
    key = UserToolPreferenceKey(UUID(int=1), "kya/togo", "claude", "data.find")
    command = McpPreferenceCommand(
        UUID(int=1),
        UUID(int=2),
        "preference-test-0001",
        "a" * 64,
        datetime.now(UTC) + timedelta(hours=1),
        "test",
    )
    assert await service.disable_tool(key, command=command, expected_revision=0) == 1
    await service.inherit_tool(key, command=command, expected_revision=1)
    with pytest.raises(ValueError, match="nonnegative"):
        await service.disable_tool(key, command=command, expected_revision=-1)
    with pytest.raises(ValueError, match="existing"):
        await service.inherit_tool(key, command=command, expected_revision=0)


def test_preference_key_requires_unit_and_tool() -> None:
    with pytest.raises(ValueError, match="required"):
        UserToolPreferenceKey(UUID(int=1), "", "", "data.find")
