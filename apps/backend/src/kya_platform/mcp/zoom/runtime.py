"""Late-bound production bridge from the KYA gateway to KYA-Zoom."""

from __future__ import annotations

from uuid import UUID, uuid7

from kya_zoom_mcp.contracts import (
    CreateMeetingRequest,
    KyaContext,
    MeetingProfile,
    PrepareMeetingRequest,
)
from kya_zoom_mcp.service import ZoomMeetingService
from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

from kya_platform.mcp.zoom.contracts import (
    CreateZoomMeetingInput,
    GetZoomMeetingInput,
    ListZoomMeetingsInput,
    PrepareZoomMeetingInput,
)


class ZoomAuthorizationAdapter:
    """The gateway guard already authorizes every call before this service runs."""

    async def require(self, context: KyaContext, permission: str) -> None:
        del context, permission


class StaticZoomConnectionResolver:
    """Resolve the configured organization host without exposing it to the client."""

    def __init__(self, host_id: str) -> None:
        self._host_id = host_id

    async def host_for(self, context: KyaContext) -> str:
        del context
        return self._host_id


class StateZoomMcpBackend:
    """Delegate to the Zoom service installed during the FastAPI lifespan."""

    def __init__(self, state: State) -> None:
        self._state = state

    def _service(self) -> ZoomMeetingService:
        service: ZoomMeetingService | None = self._state.zoom_service
        if service is None:
            raise ToolError("zoom_service_unavailable")
        return service

    @staticmethod
    def _context(unit_key: str, actor_id: UUID, correlation_id: UUID | None = None) -> KyaContext:
        return KyaContext(
            principal_id=str(actor_id),
            active_unit_id=unit_key,
            correlation_id=correlation_id or uuid7(),
        )

    async def prepare_meeting(
        self, unit_key: str, actor_id: UUID, input_data: PrepareZoomMeetingInput
    ) -> dict[str, object]:
        result = await self._service().prepare(
            self._context(unit_key, actor_id),
            PrepareMeetingRequest(
                topic=input_data.topic,
                start_time=input_data.start_time,
                duration_minutes=input_data.duration_minutes,
                timezone=input_data.timezone,
                profile=MeetingProfile(input_data.profile),
                agenda=input_data.agenda,
            ),
        )
        return result.model_dump(mode="json")

    async def create_meeting(
        self,
        unit_key: str,
        actor_id: UUID,
        input_data: CreateZoomMeetingInput,
        correlation_id: UUID,
    ) -> dict[str, object]:
        result = await self._service().create(
            self._context(unit_key, actor_id, correlation_id),
            CreateMeetingRequest(
                plan_id=input_data.plan_id,
                idempotency_key=input_data.idempotency_key,
            ),
        )
        return result.model_dump(mode="json")

    async def list_meetings(
        self, unit_key: str, actor_id: UUID, input_data: ListZoomMeetingsInput
    ) -> dict[str, object]:
        result = await self._service().list(
            self._context(unit_key, actor_id),
            page_size=input_data.page_size,
            next_page_token=input_data.next_page_token,
        )
        return result.model_dump(mode="json")

    async def get_meeting(
        self, unit_key: str, actor_id: UUID, input_data: GetZoomMeetingInput
    ) -> dict[str, object]:
        result = await self._service().get(
            self._context(unit_key, actor_id),
            input_data.meeting_id,
        )
        return result.model_dump(mode="json")


__all__ = [
    "StateZoomMcpBackend",
    "StaticZoomConnectionResolver",
    "ZoomAuthorizationAdapter",
]
