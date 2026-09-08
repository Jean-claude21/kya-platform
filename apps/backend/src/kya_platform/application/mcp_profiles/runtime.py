"""Shadowable runtime calculation for one governed MCP tool surface."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from kya_platform.authorization import AuthorizationService, ListObjectsRequest
from kya_platform.authorization.model import active_unit_context
from kya_platform.domain.mcp_profiles import (
    EffectiveToolResolver,
    ProfileToolItem,
    ToolDescriptor,
    ToolResolutionContext,
    ToolState,
)

from . import McpProfilePreferencePort


class ToolProfileMode(StrEnum):
    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class ToolProfileRequest:
    principal_id: UUID
    active_unit_key: str
    client_id: str
    oauth_scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class ToolProfileDecision:
    advertised_tool_keys: tuple[str, ...]
    effective_tool_keys: tuple[str, ...]
    revision: str
    diverged: bool
    dependency_failed: bool = False


class ToolProfileShadowSink(Protocol):
    async def record(
        self,
        *,
        request: ToolProfileRequest,
        legacy_tool_keys: tuple[str, ...],
        effective_tool_keys: tuple[str, ...],
        dependency_failed: bool,
    ) -> None: ...


class McpToolProfileRuntime:
    """Compare historical scope filtering with policy/profile filtering."""

    def __init__(
        self,
        *,
        tools: tuple[ToolDescriptor, ...],
        authorization: AuthorizationService,
        preferences: McpProfilePreferencePort,
        shadow_sink: ToolProfileShadowSink,
        mode: ToolProfileMode,
    ) -> None:
        self._tools = tools
        self._authorization = authorization
        self._preferences = preferences
        self._shadow_sink = shadow_sink
        self._mode = mode
        self._resolver = EffectiveToolResolver()

    async def resolve(self, request: ToolProfileRequest) -> ToolProfileDecision:
        legacy = tuple(
            tool.key
            for tool in self._tools
            if tool.handler_active
            and tool.lifecycle_state == "active"
            and tool.oauth_scope in request.oauth_scopes
        )
        if self._mode is ToolProfileMode.OFF:
            return ToolProfileDecision(legacy, legacy, "legacy", False)

        dependency_failed = False
        try:
            context, contextual_tuples = active_unit_context(
                user_id=str(request.principal_id),
                unit_id=request.active_unit_key,
                current_time=datetime.now(UTC),
            )
            authorized = frozenset(
                await self._authorization.list_authorized_objects(
                    ListObjectsRequest(
                        user=f"user:{request.principal_id}",
                        relation="can_invoke",
                        object_type="mcp_tool",
                        context=context,
                        contextual_tuples=contextual_tuples,
                    )
                )
            )
            disabled = await self._preferences.list_disabled_tools(
                principal_id=request.principal_id,
                active_unit_key=request.active_unit_key,
                client_id=request.client_id,
            )
            profile_items = tuple(
                ProfileToolItem("authorized-profile", key, ToolState.ENABLED, order)
                for order, key in enumerate(sorted(authorized))
            )
            resolved = self._resolver.resolve(
                self._tools,
                ToolResolutionContext(
                    oauth_scopes=request.oauth_scopes,
                    authorized_tool_keys=authorized,
                    profile_items=profile_items,
                    disabled_preferences=disabled,
                ),
            )
            effective = resolved.tool_keys
            revision = resolved.revision
        except Exception:  # authorization/storage failures must not leak tools in enforcement
            dependency_failed = True
            effective = ()
            revision = "unavailable"

        diverged = effective != legacy
        await self._shadow_sink.record(
            request=request,
            legacy_tool_keys=legacy,
            effective_tool_keys=effective,
            dependency_failed=dependency_failed,
        )
        advertised = legacy if self._mode is ToolProfileMode.SHADOW else effective
        return ToolProfileDecision(
            advertised,
            effective,
            revision,
            diverged,
            dependency_failed,
        )


__all__ = [
    "McpToolProfileRuntime",
    "ToolProfileDecision",
    "ToolProfileMode",
    "ToolProfileRequest",
    "ToolProfileShadowSink",
]
