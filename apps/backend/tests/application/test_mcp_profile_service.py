"""MCP system profile synchronization validates every bounded reference."""

import pytest

from kya_platform.application.mcp_profiles import (
    McpProfileService,
    SystemProfileRegistration,
    ToolRegistration,
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
