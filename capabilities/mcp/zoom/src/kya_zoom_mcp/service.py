"""Deterministic application service for governed Zoom meetings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from kya_zoom_mcp.contracts import (
    CreateMeetingRequest,
    CreateMeetingResult,
    KyaContext,
    MeetingList,
    MeetingPlan,
    MeetingProfile,
    MeetingRecord,
    MeetingSettings,
    PrepareMeetingRequest,
)
from kya_zoom_mcp.ports import (
    AuthorizationPort,
    MeetingPlanStore,
    OperationStore,
    ZoomConnectionResolver,
    ZoomMeetingPort,
)
from kya_zoom_mcp.time import normalize_start_time


class MeetingPlanNotFoundError(LookupError):
    pass


class MeetingPlanExpiredError(ValueError):
    pass


class MeetingPlanOwnershipError(PermissionError):
    pass


def settings_for(profile: MeetingProfile) -> MeetingSettings:
    if profile is MeetingProfile.EXTERNAL:
        return MeetingSettings(
            waiting_room=True,
            join_before_host=False,
            mute_upon_entry=True,
            participant_video=False,
            auto_recording="none",
        )
    if profile is MeetingProfile.CONFIDENTIAL:
        return MeetingSettings(
            waiting_room=True,
            join_before_host=False,
            mute_upon_entry=True,
            participant_video=False,
            auto_recording="none",
        )
    return MeetingSettings(
        waiting_room=False,
        join_before_host=True,
        mute_upon_entry=True,
        participant_video=False,
        auto_recording="none",
    )


class ZoomMeetingService:
    def __init__(
        self,
        *,
        authorization: AuthorizationPort,
        connections: ZoomConnectionResolver,
        plans: MeetingPlanStore,
        operations: OperationStore,
        zoom: ZoomMeetingPort,
    ) -> None:
        self._authorization = authorization
        self._connections = connections
        self._plans = plans
        self._operations = operations
        self._zoom = zoom

    async def prepare(self, context: KyaContext, request: PrepareMeetingRequest) -> MeetingPlan:
        await self._authorization.require(context, "zoom.meeting.create")
        normalized_start, zoom_tz = normalize_start_time(request.start_time, request.timezone)
        plan = MeetingPlan(
            plan_id=uuid4(),
            requested_by=context.principal_id,
            active_unit_id=context.active_unit_id,
            topic=" ".join(request.topic.split()),
            start_time=normalized_start,
            timezone=zoom_tz,
            duration_minutes=request.duration_minutes,
            profile=request.profile,
            agenda=request.agenda,
            settings=settings_for(request.profile),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        await self._plans.put(plan)
        return plan

    async def create(
        self, context: KyaContext, request: CreateMeetingRequest
    ) -> CreateMeetingResult:
        await self._authorization.require(context, "zoom.meeting.create")
        existing = await self._operations.get(context.principal_id, request.idempotency_key)
        if existing is not None:
            return existing

        plan = await self._plans.get(str(request.plan_id))
        if plan is None:
            raise MeetingPlanNotFoundError("meeting plan not found")
        if (
            plan.requested_by != context.principal_id
            or plan.active_unit_id != context.active_unit_id
        ):
            raise MeetingPlanOwnershipError("meeting plan belongs to another KYA context")
        if plan.expires_at <= datetime.now(UTC):
            raise MeetingPlanExpiredError("meeting plan expired; prepare a new meeting")

        host_id = await self._connections.host_for(context)
        payload: dict[str, object] = {
            "topic": plan.topic,
            "type": 2,
            "start_time": plan.start_time,
            "duration": plan.duration_minutes,
            "timezone": plan.timezone,
            "agenda": plan.agenda or "",
            "settings": plan.settings.model_dump(),
        }
        meeting = await self._zoom.create_meeting(host_id, payload)
        result = CreateMeetingResult(
            operation_id=uuid4(),
            idempotency_key=request.idempotency_key,
            meeting=meeting,
            ready_to_share=meeting.join_url is not None,
        )
        await self._operations.put(context.principal_id, request.idempotency_key, result)
        return result

    async def list(
        self,
        context: KyaContext,
        *,
        page_size: int = 30,
        next_page_token: str | None = None,
    ) -> MeetingList:
        await self._authorization.require(context, "zoom.meeting.read")
        host_id = await self._connections.host_for(context)
        return await self._zoom.list_meetings(
            host_id,
            page_size=min(max(page_size, 1), 100),
            next_page_token=next_page_token,
        )

    async def get(self, context: KyaContext, meeting_id: str) -> MeetingRecord:
        await self._authorization.require(context, "zoom.meeting.read")
        return await self._zoom.get_meeting(meeting_id)
