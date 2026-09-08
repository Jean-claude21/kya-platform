"""Idempotent PostgreSQL synchronization for MCP tools and system profiles."""

from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.mcp_profiles import (
    McpPreferenceCommand,
    McpProfileConflictError,
    McpProfileReferenceError,
    SystemProfileRegistration,
    ToolRegistration,
    UserToolPreferenceKey,
)
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    IdempotencyRecord,
    McpToolDefinition,
    McpToolProfile,
    McpToolProfileItem,
    McpUserToolPreference,
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

    async def list_disabled_tools(
        self,
        *,
        principal_id: UUID,
        active_unit_key: str,
        client_id: str,
    ) -> frozenset[str]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(McpToolDefinition.key)
                .join(
                    McpUserToolPreference,
                    McpUserToolPreference.tool_id == McpToolDefinition.id,
                )
                .where(
                    McpUserToolPreference.principal_id == principal_id,
                    McpUserToolPreference.active_unit_key == active_unit_key,
                    or_(
                        McpUserToolPreference.client_id == "",
                        McpUserToolPreference.client_id == client_id,
                    ),
                )
                .order_by(McpToolDefinition.key)
            )
            return frozenset(result)

    async def disable_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        command: McpPreferenceCommand,
        expected_revision: int,
    ) -> int:
        try:
            async with self._sessions() as session, session.begin():
                scope = self._preference_scope("disable", key)
                replay = await self._replay_revision(session, scope, command)
                if replay is not None:
                    return replay
                tool_id = await session.scalar(
                    select(McpToolDefinition.id).where(McpToolDefinition.key == key.tool_key)
                )
                if tool_id is None:
                    raise McpProfileReferenceError("MCP tool does not exist")
                identity = {
                    "principal_id": key.principal_id,
                    "active_unit_key": key.active_unit_key,
                    "client_id": key.client_id,
                    "tool_id": tool_id,
                }
                row = await session.scalar(
                    select(McpUserToolPreference)
                    .where(
                        *(
                            getattr(McpUserToolPreference, name) == value
                            for name, value in identity.items()
                        )
                    )
                    .with_for_update()
                )
                current_revision = 0 if row is None else row.revision
                if current_revision != expected_revision:
                    raise McpProfileConflictError("MCP preference revision is stale")
                if row is None:
                    session.add(
                        McpUserToolPreference(
                            **identity,
                            state="disabled",
                            revision=1,
                            updated_by=command.actor_id,
                        )
                    )
                    self._remember_preference(session, scope, command, key, 1, "disabled")
                    return 1
                row.revision += 1
                row.updated_by = command.actor_id
                self._remember_preference(session, scope, command, key, row.revision, "disabled")
                return row.revision
        except IntegrityError as error:
            raise McpProfileConflictError("MCP preference was created concurrently") from error

    async def inherit_tool(
        self,
        key: UserToolPreferenceKey,
        *,
        command: McpPreferenceCommand,
        expected_revision: int,
    ) -> None:
        async with self._sessions() as session, session.begin():
            scope = self._preference_scope("inherit", key)
            replay = await self._replay_revision(session, scope, command)
            if replay is not None:
                return
            tool_id = await session.scalar(
                select(McpToolDefinition.id).where(McpToolDefinition.key == key.tool_key)
            )
            if tool_id is None:
                raise McpProfileReferenceError("MCP tool does not exist")
            result = cast(
                CursorResult[Any],
                await session.execute(
                    delete(McpUserToolPreference).where(
                        McpUserToolPreference.principal_id == key.principal_id,
                        McpUserToolPreference.active_unit_key == key.active_unit_key,
                        McpUserToolPreference.client_id == key.client_id,
                        McpUserToolPreference.tool_id == tool_id,
                        McpUserToolPreference.revision == expected_revision,
                    )
                ),
            )
            if result.rowcount != 1:
                raise McpProfileConflictError("MCP preference revision is stale")
            self._remember_preference(session, scope, command, key, 0, "inherited")

    @staticmethod
    def _preference_scope(action: str, key: UserToolPreferenceKey) -> str:
        return (
            f"mcp:preference:{action}:{key.principal_id}:"
            f"{key.active_unit_key}:{key.client_id}:{key.tool_key}"
        )[:255]

    @staticmethod
    async def _replay_revision(
        session: AsyncSession,
        scope: str,
        command: McpPreferenceCommand,
    ) -> int | None:
        record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == command.idempotency_key,
            )
        )
        if record is None:
            return None
        if record.request_hash != command.request_hash:
            raise McpProfileConflictError("idempotency key belongs to another request")
        revision = record.response_body.get("revision")
        if not isinstance(revision, int):
            raise McpProfileConflictError("idempotency evidence is invalid")
        return revision

    @staticmethod
    def _remember_preference(
        session: AsyncSession,
        scope: str,
        command: McpPreferenceCommand,
        key: UserToolPreferenceKey,
        revision: int,
        state: str,
    ) -> None:
        session.add(
            IdempotencyRecord(
                scope=scope,
                idempotency_key=command.idempotency_key,
                request_hash=command.request_hash,
                response_status=200 if state == "disabled" else 204,
                response_body={"revision": revision},
                expires_at=command.expires_at,
            )
        )
        session.add(
            AuditEvent(
                actor_id=command.actor_id,
                action=f"mcp.preference.{state}",
                target_type="mcp_tool",
                target_id=key.tool_key,
                scope=f"workspace:{key.active_unit_key}",
                environment=command.environment,
                decision="allowed",
                outcome="succeeded",
                correlation_id=command.correlation_id,
                event_metadata={
                    "client_id": key.client_id or "all",
                    "revision": revision,
                },
            )
        )


__all__ = ["SqlAlchemyMcpProfileRegistry"]
