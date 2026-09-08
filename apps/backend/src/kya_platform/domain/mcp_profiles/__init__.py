"""Deterministic composition of MCP tools; profiles can only narrow authorization."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256


class ToolProfileError(ValueError):
    """The requested effective tool set violates a profile invariant."""


class ToolState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    key: str
    namespace: str
    oauth_scope: str
    handler_active: bool = True
    lifecycle_state: str = "active"


@dataclass(frozen=True, slots=True)
class ProfileToolItem:
    profile_key: str
    tool_key: str
    state: ToolState
    sort_order: int = 0

    def __post_init__(self) -> None:
        if self.sort_order < 0:
            raise ToolProfileError("tool profile sort order must be nonnegative")


@dataclass(frozen=True, slots=True)
class ToolResolutionContext:
    oauth_scopes: frozenset[str]
    authorized_tool_keys: frozenset[str]
    profile_items: tuple[ProfileToolItem, ...]
    disabled_preferences: frozenset[str] = frozenset()
    inherit_when_unassigned: bool = False
    maximum_tools: int = 24

    def __post_init__(self) -> None:
        if self.maximum_tools < 1 or self.maximum_tools > 24:
            raise ToolProfileError("maximum effective MCP tools must be between 1 and 24")


@dataclass(frozen=True, slots=True)
class EffectiveToolSet:
    tool_keys: tuple[str, ...]
    revision: str


class EffectiveToolResolver:
    """Intersect active handlers, scopes, grants and profiles with explicit denials."""

    def resolve(
        self,
        tools: tuple[ToolDescriptor, ...],
        context: ToolResolutionContext,
    ) -> EffectiveToolSet:
        duplicate_keys = len({tool.key for tool in tools}) != len(tools)
        if duplicate_keys:
            raise ToolProfileError("MCP tool keys must be unique")

        candidates = {
            tool.key: tool
            for tool in tools
            if tool.handler_active
            and tool.lifecycle_state == "active"
            and tool.oauth_scope in context.oauth_scopes
            and tool.key in context.authorized_tool_keys
        }
        enabled = {
            item.tool_key for item in context.profile_items if item.state is ToolState.ENABLED
        }
        disabled = {
            item.tool_key for item in context.profile_items if item.state is ToolState.DISABLED
        } | set(context.disabled_preferences)
        if context.profile_items or not context.inherit_when_unassigned:
            candidates = {key: tool for key, tool in candidates.items() if key in enabled}
        candidates = {key: tool for key, tool in candidates.items() if key not in disabled}

        if len(candidates) > context.maximum_tools:
            raise ToolProfileError("effective MCP tool set exceeds its configured maximum")

        sort_orders: dict[str, int] = {}
        for item in context.profile_items:
            if item.state is ToolState.ENABLED:
                previous = sort_orders.get(item.tool_key)
                sort_orders[item.tool_key] = (
                    item.sort_order if previous is None else min(previous, item.sort_order)
                )
        ordered = tuple(
            key
            for key, _ in sorted(
                candidates.items(),
                key=lambda pair: (
                    sort_orders.get(pair[0], 2**31 - 1),
                    pair[1].namespace,
                    pair[0],
                ),
            )
        )
        evidence = {
            "tools": ordered,
            "scopes": sorted(context.oauth_scopes),
            "authorized": sorted(context.authorized_tool_keys),
            "profiles": [
                (item.profile_key, item.tool_key, item.state.value, item.sort_order)
                for item in sorted(
                    context.profile_items,
                    key=lambda item: (
                        item.profile_key,
                        item.sort_order,
                        item.tool_key,
                        item.state.value,
                    ),
                )
            ],
            "preferences": sorted(context.disabled_preferences),
        }
        revision = sha256(
            json.dumps(evidence, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return EffectiveToolSet(ordered, revision)


__all__ = [
    "EffectiveToolResolver",
    "EffectiveToolSet",
    "ProfileToolItem",
    "ToolDescriptor",
    "ToolProfileError",
    "ToolResolutionContext",
    "ToolState",
]
