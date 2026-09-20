from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from kya_zoom_mcp.contracts import (
    CreateMeetingRequest,
    KyaContext,
    MeetingList,
    MeetingPlan,
    MeetingProfile,
    MeetingRecord,
    MeetingSettings,
    PrepareMeetingRequest,
)
from kya_zoom_mcp.service import MeetingPlanOwnershipError, ZoomMeetingService
from kya_zoom_mcp.stores import MemoryMeetingPlanStore, MemoryOperationStore


class RecordingAuthorization:
    def __init__(self) -> None:
        self.permissions: list[str] = []

    async def require(self, context: KyaContext, permission: str) -> None:
        self.permissions.append(permission)


class StaticConnections:
    async def host_for(self, context: KyaContext) -> str:
        return "zoom-host@example.com"


class RecordingZoom:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, dict[str, object]]] = []

    async def create_meeting(self, host_id: str, payload: dict[str, object]) -> MeetingRecord:
        self.create_calls.append((host_id, payload))
        return MeetingRecord(
            meeting_id="123456789",
            topic=str(payload["topic"]),
            start_time=str(payload["start_time"]),
            timezone=str(payload["timezone"]),
            duration_minutes=int(payload["duration"]),
            join_url="https://zoom.us/j/123456789",
            passcode="safe-to-share",
        )

    async def list_meetings(
        self, host_id: str, *, page_size: int, next_page_token: str | None
    ) -> MeetingList:
        return MeetingList(items=[])

    async def get_meeting(self, meeting_id: str) -> MeetingRecord:
        return MeetingRecord(meeting_id=meeting_id, topic="Point projet")


def context(*, principal_id: str = "person-1", unit_id: str = "unit-togo") -> KyaContext:
    return KyaContext(
        principal_id=principal_id,
        active_unit_id=unit_id,
        workspace_id="workspace-platform",
        correlation_id=uuid4(),
    )


def build_service() -> tuple[ZoomMeetingService, RecordingAuthorization, RecordingZoom]:
    authorization = RecordingAuthorization()
    zoom = RecordingZoom()
    service = ZoomMeetingService(
        authorization=authorization,
        connections=StaticConnections(),
        plans=MemoryMeetingPlanStore(),
        operations=MemoryOperationStore(),
        zoom=zoom,
    )
    return service, authorization, zoom


async def test_prepare_external_meeting_applies_policy_and_normalizes_lome() -> None:
    service, authorization, _ = build_service()

    plan = await service.prepare(
        context(),
        PrepareMeetingRequest(
            topic="  Démonstration   client  ",
            start_time="2026-09-21T10:00:00",
            duration_minutes=45,
            timezone="Africa/Lome",
            profile=MeetingProfile.EXTERNAL,
        ),
    )

    assert authorization.permissions == ["zoom.meeting.create"]
    assert plan.topic == "Démonstration client"
    assert plan.timezone == "UTC"
    assert plan.settings.waiting_room is True
    assert plan.settings.join_before_host is False
    assert plan.confirmation_required is True


async def test_create_is_idempotent_and_returns_only_safe_projection() -> None:
    service, _, zoom = build_service()
    kya_context = context()
    plan = await service.prepare(
        kya_context,
        PrepareMeetingRequest(
            topic="Comité projet",
            start_time="2026-09-21T10:00:00Z",
            duration_minutes=30,
        ),
    )
    request = CreateMeetingRequest(
        plan_id=plan.plan_id,
        idempotency_key="meeting-demo-20260921",
    )

    first = await service.create(kya_context, request)
    second = await service.create(kya_context, request)

    assert first == second
    assert len(zoom.create_calls) == 1
    assert first.meeting.join_url is not None
    assert "start_url" not in first.model_dump(mode="json")


async def test_plan_cannot_be_used_from_another_identity() -> None:
    service, _, _ = build_service()
    plan = await service.prepare(
        context(),
        PrepareMeetingRequest(
            topic="Comité projet",
            start_time="2026-09-21T10:00:00Z",
            duration_minutes=30,
        ),
    )

    with pytest.raises(MeetingPlanOwnershipError):
        await service.create(
            context(principal_id="person-2"),
            CreateMeetingRequest(plan_id=plan.plan_id, idempotency_key="other-user-attempt"),
        )


async def test_expired_plan_is_rejected() -> None:
    plans = MemoryMeetingPlanStore()
    zoom = RecordingZoom()
    service = ZoomMeetingService(
        authorization=RecordingAuthorization(),
        connections=StaticConnections(),
        plans=plans,
        operations=MemoryOperationStore(),
        zoom=zoom,
    )
    expired = MeetingPlan(
        plan_id=uuid4(),
        requested_by="person-1",
        active_unit_id="unit-togo",
        topic="Expired",
        start_time="2026-09-21T10:00:00Z",
        timezone="UTC",
        duration_minutes=30,
        profile=MeetingProfile.INTERNAL,
        agenda=None,
        settings=MeetingSettings(
            waiting_room=False,
            join_before_host=True,
            mute_upon_entry=True,
            participant_video=False,
            auto_recording="none",
        ),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    await plans.put(expired)

    with pytest.raises(ValueError, match="expired"):
        await service.create(
            context(),
            CreateMeetingRequest(plan_id=expired.plan_id, idempotency_key="expired-plan-test"),
        )
