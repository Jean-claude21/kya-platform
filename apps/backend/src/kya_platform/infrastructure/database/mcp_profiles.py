"""Idempotent PostgreSQL synchronization for MCP tools and system profiles."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.mcp_profiles import (
    SystemProfileRegistration,
    ToolRegistration,
)
from kya_platform.infrastructure.database.models import (
    McpToolDefinition,
    McpToolProfile,
    McpToolProfileItem,
)

SYSTEM_ACTOR = UUID(int=0)


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://kya-platform.vttlife.com/{kind}/{key}")


class SqlAlchemyMcpProfileRegistry:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def synchronize(
        self,
        tools: tuple[ToolRegistration, ...],
        profiles: tuple[SystemProfileRegistration, ...],
    ) -> None:
        tool_ids = {tool.key: _stable_id("mcp/tools", tool.key) for tool in tools}
        async with self._sessions.begin() as session:
            for tool in tools:
                values = {
                    "id": tool_ids[tool.key],
                    "key": tool.key,
                    "namespace": tool.namespace,
                    "display_name": tool.display_name,
                    "description": tool.description,
                    "oauth_scope": tool.oauth_scope,
                    "target_object_type": tool.target_object_type,
                    "target_relation": tool.target_relation,
                    "risk": tool.risk,
                    "is_write": tool.is_write,
                    "requires_confirmation": tool.requires_confirmation,
                    "requires_idempotency": tool.requires_idempotency,
                    "handler_key": tool.key,
                    "lifecycle_state": "active",
                }
                await session.execute(
                    insert(McpToolDefinition)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=[McpToolDefinition.key],
                        set_={
                            key: value for key, value in values.items() if key not in {"id", "key"}
                        },
                    )
                )

            for profile in profiles:
                profile_id = _stable_id("mcp/profiles", profile.key)
                values = {
                    "id": profile_id,
                    "key": profile.key,
                    "name": profile.name,
                    "description": profile.description,
                    "kind": "system",
                    "status": "active",
                    "version": 1,
                    "revision": 1,
                    "max_active_tools": 24,
                    "created_by": SYSTEM_ACTOR,
                }
                await session.execute(
                    insert(McpToolProfile)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=[McpToolProfile.key],
                        set_={
                            "name": profile.name,
                            "description": profile.description,
                            "status": "active",
                        },
                    )
                )
                expected_ids = [tool_ids[key] for key in profile.tool_keys]
                await session.execute(
                    delete(McpToolProfileItem).where(
                        McpToolProfileItem.profile_id == profile_id,
                        McpToolProfileItem.tool_id.not_in(expected_ids),
                    )
                )
                for order, tool_key in enumerate(profile.tool_keys):
                    await session.execute(
                        insert(McpToolProfileItem)
                        .values(
                            profile_id=profile_id,
                            tool_id=tool_ids[tool_key],
                            state="enabled",
                            sort_order=order,
                            configured_by=SYSTEM_ACTOR,
                        )
                        .on_conflict_do_update(
                            index_elements=[
                                McpToolProfileItem.profile_id,
                                McpToolProfileItem.tool_id,
                            ],
                            set_={"state": "enabled", "sort_order": order},
                        )
                    )


__all__ = ["SqlAlchemyMcpProfileRegistry"]
