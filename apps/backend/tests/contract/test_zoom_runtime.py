from uuid import UUID, uuid4

import pytest
from kya_zoom_mcp.contracts import MeetingList, MeetingRecord
from kya_zoom_mcp.service import ZoomMeetingService
from kya_zoom_mcp.stores import MemoryMeetingPlanStore, MemoryOperationStore
from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

from kya_platform.mcp.zoom.contracts import (
    CreateZoomMeetingInput,
    GetZoomMeetingInput,
    ListZoomMeetingsInput,
    PrepareZoomMeetingInput,
)
from kya_platform.mcp.zoom.runtime import (
    StateZoomMcpBackend,
    StaticZoomConnectionResolver,
    ZoomAuthorizationAdapter,
)


class DummyZoom:
    async def create_meeting(self, host_id: str, payload: dict[str, object]) -> MeetingRecord:
        assert host_id == "me"
        return MeetingRecord(
            meeting_id="123",
            topic=str(payload["topic"]),
            join_url="https://zoom.us/j/123",
        )

    async def list_meetings(
        self, host_id: str, *, page_size: int, next_page_token: str | None
    ) -> MeetingList:
        assert host_id == "me"
        return MeetingList(items=[], next_page_token=next_page_token)

    async def get_meeting(self, meeting_id: str) -> MeetingRecord:
        return MeetingRecord(meeting_id=meeting_id, topic="Point KYA")


@pytest.mark.asyncio
async def test_state_zoom_backend_runs_complete_meeting_flow() -> None:
    state = State()
    state.zoom_service = ZoomMeetingService(
        authorization=ZoomAuthorizationAdapter(),
        connections=StaticZoomConnectionResolver("me"),
        plans=MemoryMeetingPlanStore(),
        operations=MemoryOperationStore(),
        zoom=DummyZoom(),
    )
    backend = StateZoomMcpBackend(state)
    actor = uuid4()

    plan = await backend.prepare_meeting(
        "groupe",
        actor,
        PrepareZoomMeetingInput(
            topic="Point KYA",
            start_time="2026-09-22T10:00:00+00:00",
            duration_minutes=45,
        ),
    )
    created = await backend.create_meeting(
        "groupe",
        actor,
        CreateZoomMeetingInput(
            plan_id=str(plan["plan_id"]),
            idempotency_key="point-kya-20260922",
        ),
        UUID("0191c49b-7377-7890-a123-456789abcdef"),
    )
    listed = await backend.list_meetings("groupe", actor, ListZoomMeetingsInput())
    fetched = await backend.get_meeting("groupe", actor, GetZoomMeetingInput(meeting_id="123"))

    assert created["ready_to_share"] is True
    assert listed == {"items": [], "next_page_token": None}
    assert fetched["meeting_id"] == "123"


@pytest.mark.asyncio
async def test_state_zoom_backend_fails_closed_without_runtime() -> None:
    state = State()
    state.zoom_service = None
    backend = StateZoomMcpBackend(state)

    with pytest.raises(ToolError, match="zoom_service_unavailable"):
        await backend.list_meetings("groupe", uuid4(), ListZoomMeetingsInput())
