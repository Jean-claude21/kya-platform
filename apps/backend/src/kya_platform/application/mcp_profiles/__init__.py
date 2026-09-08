"""Application contracts for the MCP tool control plane."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ToolRegistration:
    key: str
    namespace: str
    display_name: str
    description: str
    oauth_scope: str
    target_object_type: str
    target_relation: str
    risk: str
    is_write: bool
    requires_confirmation: bool
    requires_idempotency: bool


@dataclass(frozen=True, slots=True)
class SystemProfileRegistration:
    key: str
    name: str
    description: str
    tool_keys: tuple[str, ...]


class McpProfileRegistryPort(Protocol):
    async def synchronize(
        self,
        tools: tuple[ToolRegistration, ...],
        profiles: tuple[SystemProfileRegistration, ...],
    ) -> None: ...


class McpProfileConflictError(RuntimeError):
    """A preference mutation used a stale optimistic revision."""


class McpProfileReferenceError(ValueError):
    """A profile mutation references an unknown tool."""


@dataclass(frozen=True, slots=True)
class UserToolPreferenceKey:
    principal_id: UUID
    active_unit_key: str
    client_id: str
    tool_key: str

    def __post_init__(self) -> None:
        if not self.active_unit_key.strip() or not self.tool_key.strip():
            raise ValueError("unit and tool keys are required")


class McpProfilePreferencePort(Protocol):
    async def list_disabled_tools(
        self,
        *,
        principal_id: UUID,
        active_unit_key: str,
        client_id: str,
    ) -> frozenset[str]: ...

    async def disable_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        actor_id: UUID,
        expected_revision: int,
    ) -> int: ...

    async def inherit_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        expected_revision: int,
    ) -> None: ...


class McpProfileService:
    def __init__(self, registry: McpProfileRegistryPort) -> None:
        self._registry = registry

    async def synchronize(
        self,
        tools: tuple[ToolRegistration, ...],
        profiles: tuple[SystemProfileRegistration, ...],
    ) -> None:
        known = {tool.key for tool in tools}
        if len(known) != len(tools):
            raise ValueError("MCP tool registration keys must be unique")
        for profile in profiles:
            if not profile.tool_keys or not set(profile.tool_keys) <= known:
                raise ValueError("MCP system profile references unknown tools")
            if len(profile.tool_keys) > 24:
                raise ValueError("MCP system profile exceeds the 24-tool limit")
        await self._registry.synchronize(tools, profiles)


class McpPreferenceService:
    """Restrict a user's tools; intentionally exposes no enable operation."""

    def __init__(self, repository: McpProfilePreferencePort) -> None:
        self._repository = repository

    async def disable_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        actor_id: UUID,
        expected_revision: int,
    ) -> int:
        if expected_revision < 0:
            raise ValueError("expected revision must be nonnegative")
        return await self._repository.disable_tool(
            key,
            actor_id=actor_id,
            expected_revision=expected_revision,
        )

    async def inherit_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        expected_revision: int,
    ) -> None:
        if expected_revision < 1:
            raise ValueError("an inherited preference must replace an existing revision")
        await self._repository.inherit_tool(key, expected_revision=expected_revision)


__all__ = [
    "McpPreferenceService",
    "McpProfileConflictError",
    "McpProfilePreferencePort",
    "McpProfileReferenceError",
    "McpProfileRegistryPort",
    "McpProfileService",
    "SystemProfileRegistration",
    "ToolRegistration",
    "UserToolPreferenceKey",
]
