"""Shadow mode proves differences before MCP tool enforcement is enabled."""

from uuid import UUID

import pytest

from kya_platform.application.mcp_profiles.runtime import (
    McpToolProfileRuntime,
    ToolProfileMode,
    ToolProfileRequest,
)
from kya_platform.authorization import AuthorizationService
from kya_platform.domain.mcp_profiles import ToolDescriptor


class Policy:
    def __init__(self, objects: tuple[str, ...] = (), *, failing: bool = False) -> None:
        self.objects = objects
        self.failing = failing
        self.calls = 0

    async def list_objects(self, request: object) -> tuple[str, ...]:
        self.calls += 1
        if self.failing:
            raise RuntimeError("policy unavailable")
        return self.objects

    async def check(self, request: object) -> object:
        raise AssertionError("profile resolution must use one list operation")


class Preferences:
    def __init__(self, disabled: frozenset[str] = frozenset()) -> None:
        self.disabled = disabled

    async def list_disabled_tools(self, **kwargs: object) -> frozenset[str]:
        return self.disabled

    async def disable_tool(self, *args: object, **kwargs: object) -> int:
        raise AssertionError

    async def inherit_tool(self, *args: object, **kwargs: object) -> None:
        raise AssertionError


class Sink:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    async def record(self, **values: object) -> None:
        self.records.append(values)


TOOLS = (
    ToolDescriptor("data.find", "data", "data:read"),
    ToolDescriptor("data.start", "data", "data:write"),
)
REQUEST = ToolProfileRequest(
    UUID(int=1), "kya/togo/cvsi", "claude", frozenset({"data:read", "data:write"})
)


def runtime(
    mode: ToolProfileMode,
    policy: Policy,
    preferences: Preferences,
    sink: Sink,
) -> McpToolProfileRuntime:
    return McpToolProfileRuntime(
        tools=TOOLS,
        authorization=AuthorizationService(policy),  # type: ignore[arg-type]
        preferences=preferences,  # type: ignore[arg-type]
        shadow_sink=sink,
        mode=mode,
    )


@pytest.mark.asyncio
async def test_shadow_records_difference_but_preserves_legacy_list() -> None:
    sink = Sink()
    policy = Policy(("mcp_tool:data.find",))
    decision = await runtime(ToolProfileMode.SHADOW, policy, Preferences(), sink).resolve(REQUEST)
    assert decision.advertised_tool_keys == ("data.find", "data.start")
    assert decision.effective_tool_keys == ("data.find",)
    assert decision.diverged
    assert policy.calls == 1
    assert len(sink.records) == 1


@pytest.mark.asyncio
async def test_enforcement_applies_authorization_and_personal_disable() -> None:
    sink = Sink()
    decision = await runtime(
        ToolProfileMode.ENFORCE,
        Policy(("mcp_tool:data.find", "mcp_tool:data.start")),
        Preferences(frozenset({"data.start"})),
        sink,
    ).resolve(REQUEST)
    assert decision.advertised_tool_keys == ("data.find",)
    assert not decision.dependency_failed


@pytest.mark.asyncio
async def test_enforcement_fails_closed_while_shadow_preserves_service() -> None:
    enforce = await runtime(
        ToolProfileMode.ENFORCE, Policy(failing=True), Preferences(), Sink()
    ).resolve(REQUEST)
    shadow = await runtime(
        ToolProfileMode.SHADOW, Policy(failing=True), Preferences(), Sink()
    ).resolve(REQUEST)
    assert enforce.advertised_tool_keys == ()
    assert enforce.dependency_failed
    assert shadow.advertised_tool_keys == ("data.find", "data.start")
    assert shadow.dependency_failed


@pytest.mark.asyncio
async def test_off_mode_has_no_policy_or_storage_dependency() -> None:
    policy = Policy(failing=True)
    decision = await runtime(ToolProfileMode.OFF, policy, Preferences(), Sink()).resolve(REQUEST)
    assert decision.advertised_tool_keys == ("data.find", "data.start")
    assert policy.calls == 0
