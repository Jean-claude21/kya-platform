"""MCP profile composition is restrictive, deterministic and bounded."""

import pytest

from kya_platform.domain.mcp_profiles import (
    EffectiveToolResolver,
    ProfileToolItem,
    ToolDescriptor,
    ToolProfileError,
    ToolResolutionContext,
    ToolState,
)


def tool(key: str, scope: str = "data:read", namespace: str = "data") -> ToolDescriptor:
    return ToolDescriptor(key, namespace, scope)


def context(
    *items: ProfileToolItem,
    scopes: frozenset[str] = frozenset({"data:read"}),
    authorized: frozenset[str] = frozenset({"find", "read", "write"}),
    disabled: frozenset[str] = frozenset(),
    inherit: bool = False,
    maximum: int = 24,
) -> ToolResolutionContext:
    return ToolResolutionContext(scopes, authorized, items, disabled, inherit, maximum)


def enabled(profile: str, key: str, order: int = 0) -> ProfileToolItem:
    return ProfileToolItem(profile, key, ToolState.ENABLED, order)


def disabled(profile: str, key: str) -> ProfileToolItem:
    return ProfileToolItem(profile, key, ToolState.DISABLED)


def test_intersects_handlers_scopes_grants_and_profiles() -> None:
    tools = (
        tool("find"),
        tool("read", "catalog:read", "catalog"),
        tool("write", "data:write"),
        ToolDescriptor("retired", "data", "data:read", lifecycle_state="retired"),
        ToolDescriptor("missing-handler", "data", "data:read", handler_active=False),
    )

    result = EffectiveToolResolver().resolve(
        tools,
        context(enabled("reader", "find"), enabled("reader", "read")),
    )

    assert result.tool_keys == ("find",)


def test_disabled_from_any_profile_and_personal_preference_win() -> None:
    tools = (tool("find"), tool("read"), tool("write"))
    result = EffectiveToolResolver().resolve(
        tools,
        context(
            enabled("reader", "find"),
            enabled("reader", "read"),
            enabled("operator", "write"),
            disabled("restricted", "read"),
            disabled=frozenset({"write"}),
        ),
    )
    assert result.tool_keys == ("find",)


def test_no_profile_fails_closed_except_during_explicit_shadow_inheritance() -> None:
    tools = (tool("find"),)
    assert EffectiveToolResolver().resolve(tools, context()).tool_keys == ()
    assert EffectiveToolResolver().resolve(tools, context(inherit=True)).tool_keys == ("find",)


def test_order_and_revision_are_stable_across_input_order() -> None:
    tools = (tool("zeta"), tool("alpha"), tool("beta", namespace="catalog"))
    items = (
        enabled("reader", "zeta", 2),
        enabled("reader", "alpha", 1),
        enabled("reader", "beta", 1),
    )
    first = EffectiveToolResolver().resolve(
        tools, context(*items, authorized=frozenset({"zeta", "alpha", "beta"}))
    )
    second = EffectiveToolResolver().resolve(
        tuple(reversed(tools)),
        context(*reversed(items), authorized=frozenset({"beta", "alpha", "zeta"})),
    )
    assert first.tool_keys == ("beta", "alpha", "zeta")
    assert second == first


def test_rejects_duplicate_keys_invalid_limits_and_tool_overflow() -> None:
    with pytest.raises(ToolProfileError, match="unique"):
        EffectiveToolResolver().resolve((tool("find"), tool("find")), context(inherit=True))
    with pytest.raises(ToolProfileError, match="between 1 and 24"):
        context(maximum=25)
    tools = tuple(tool(f"tool-{index}") for index in range(2))
    with pytest.raises(ToolProfileError, match="exceeds"):
        EffectiveToolResolver().resolve(
            tools,
            context(
                *(enabled("reader", item.key, index) for index, item in enumerate(tools)),
                authorized=frozenset(item.key for item in tools),
                maximum=1,
            ),
        )


def test_rejects_negative_profile_sort_order() -> None:
    with pytest.raises(ToolProfileError, match="nonnegative"):
        enabled("reader", "find", -1)
