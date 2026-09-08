"""Application contracts for the MCP tool control plane."""

from dataclasses import dataclass
from typing import Protocol


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


__all__ = [
    "McpProfileRegistryPort",
    "McpProfileService",
    "SystemProfileRegistration",
    "ToolRegistration",
]
