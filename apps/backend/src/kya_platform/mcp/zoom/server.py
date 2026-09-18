"""Register governed Zoom capabilities on the KYA MCP gateway."""

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar
from uuid import UUID, uuid7

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.mcp.data.server import DataMcpAuditSink
from kya_platform.mcp.registry.server import RegistryGuard
from kya_platform.mcp.zoom.contracts import (
    CreateZoomMeetingInput,
    GetZoomMeetingInput,
    ListZoomMeetingsInput,
    PrepareZoomMeetingInput,
)

T = TypeVar("T")


class ZoomMcpBackend(Protocol):
    async def prepare_meeting(
        self, unit_key: str, actor_id: UUID, input_data: PrepareZoomMeetingInput
    ) -> dict[str, object]: ...

    async def create_meeting(
        self,
        unit_key: str,
        actor_id: UUID,
        input_data: CreateZoomMeetingInput,
        correlation_id: UUID,
    ) -> dict[str, object]: ...

    async def list_meetings(
        self, unit_key: str, actor_id: UUID, input_data: ListZoomMeetingsInput
    ) -> dict[str, object]: ...

    async def get_meeting(
        self, unit_key: str, actor_id: UUID, input_data: GetZoomMeetingInput
    ) -> dict[str, object]: ...


class GovernedZoomExecution:
    def __init__(self, guard: RegistryGuard, audit: DataMcpAuditSink) -> None:
        self._guard = guard
        self._audit = audit

    async def run(
        self,
        tool_name: str,
        *,
        target_type: str,
        target_id: str,
        operation: Callable[[str, UUID, UUID], Awaitable[T]],
    ) -> T:
        await self._audit.ensure_available()
        actor_id = self._guard.principal_id(tool_name)
        active_unit = self._guard.active_unit(tool_name)
        correlation_id = uuid7()
        try:
            await self._guard.require(tool_name, active_unit)
        except ToolError:
            await self._audit.record(
                actor_id=actor_id,
                active_unit=active_unit,
                tool_name=tool_name,
                target_type=target_type,
                target_id=target_id,
                decision="denied",
                outcome="rejected",
                correlation_id=correlation_id,
            )
            raise
        try:
            result = await operation(active_unit, actor_id, correlation_id)
        except Exception:
            await self._audit.record(
                actor_id=actor_id,
                active_unit=active_unit,
                tool_name=tool_name,
                target_type=target_type,
                target_id=target_id,
                decision="allowed",
                outcome="failed",
                correlation_id=correlation_id,
            )
            raise
        await self._audit.record(
            actor_id=actor_id,
            active_unit=active_unit,
            tool_name=tool_name,
            target_type=target_type,
            target_id=target_id,
            decision="allowed",
            outcome="succeeded",
            correlation_id=correlation_id,
        )
        return result


def register_zoom_tools(
    server: MCPServer[None],
    *,
    backend: ZoomMcpBackend,
    guard: RegistryGuard,
    audit: DataMcpAuditSink,
) -> None:
    """Expose Zoom meeting operations without leaking privileged start URLs."""

    execution = GovernedZoomExecution(guard, audit)

    @server.tool(name="prepare_zoom_meeting", structured_output=True)
    async def prepare_zoom_meeting(
        topic: str,
        start_time: str,
        duration_minutes: int,
        timezone: str = "Africa/Lome",
        profile: str = "internal",
        agenda: str | None = None,
    ) -> dict[str, object]:
        """Valider et préparer une réunion Zoom sans encore la créer."""
        payload = PrepareZoomMeetingInput(
            topic=topic,
            start_time=start_time,
            duration_minutes=duration_minutes,
            timezone=timezone,
            profile=profile,
            agenda=agenda,
        )

        async def prepare(unit: str, actor: UUID, correlation: UUID) -> dict[str, object]:
            del correlation
            return await backend.prepare_meeting(unit, actor, payload)

        return await execution.run(
            "prepare_zoom_meeting",
            target_type="zoom_meeting_plan",
            target_id=topic,
            operation=prepare,
        )

    @server.tool(name="create_zoom_meeting", structured_output=True)
    async def create_zoom_meeting(
        plan_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        """Créer une réunion Zoom à partir d'un plan préparé et confirmé."""
        payload = CreateZoomMeetingInput(
            plan_id=plan_id,
            idempotency_key=idempotency_key,
        )

        async def create(unit: str, actor: UUID, correlation: UUID) -> dict[str, object]:
            return await backend.create_meeting(unit, actor, payload, correlation)

        return await execution.run(
            "create_zoom_meeting",
            target_type="zoom_meeting",
            target_id=plan_id,
            operation=create,
        )

    @server.tool(name="list_zoom_meetings", structured_output=True)
    async def list_zoom_meetings(
        page_size: int = 30,
        next_page_token: str | None = None,
    ) -> dict[str, object]:
        """Lister les réunions Zoom autorisées pour l'unité active."""
        payload = ListZoomMeetingsInput(
            page_size=page_size,
            next_page_token=next_page_token,
        )

        async def list_m(unit: str, actor: UUID, correlation: UUID) -> dict[str, object]:
            del correlation
            return await backend.list_meetings(unit, actor, payload)

        return await execution.run(
            "list_zoom_meetings",
            target_type="zoom_meeting_list",
            target_id=unit_active
            if (unit_active := guard.active_unit("list_zoom_meetings"))
            else "active-unit",
            operation=list_m,
        )

    @server.tool(name="get_zoom_meeting", structured_output=True)
    async def get_zoom_meeting(
        meeting_id: str,
    ) -> dict[str, object]:
        """Consulter une réunion Zoom (projection sécurisée sans start_url hôte)."""
        payload = GetZoomMeetingInput(meeting_id=meeting_id)

        async def get_m(unit: str, actor: UUID, correlation: UUID) -> dict[str, object]:
            del correlation
            return await backend.get_meeting(unit, actor, payload)

        return await execution.run(
            "get_zoom_meeting",
            target_type="zoom_meeting",
            target_id=meeting_id,
            operation=get_m,
        )


__all__ = ["GovernedZoomExecution", "ZoomMcpBackend", "register_zoom_tools"]
