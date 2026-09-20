from typing import ClassVar
from uuid import UUID

import pytest
from mcp.server.mcpserver import MCPServer

from kya_platform.authorization import AuthorizationDecision, AuthorizationService, CheckRequest
from kya_platform.mcp.registry.server import RegistryGuard
from kya_platform.mcp.zoom.contracts import (
    CreateZoomMeetingInput,
    GetZoomMeetingInput,
    ListZoomMeetingsInput,
    PrepareZoomMeetingInput,
)
from kya_platform.mcp.zoom.server import register_zoom_tools


class DummyAuditSink:
    async def ensure_available(self) -> None:
        pass

    async def record(self, **kwargs: object) -> None:
        pass


class DummyZoomBackend:
    async def prepare_meeting(
        self, unit_key: str, actor_id: UUID, input_data: PrepareZoomMeetingInput
    ) -> dict[str, object]:
        return {"plan_id": "plan-123", "topic": input_data.topic, "status": "prepared"}

    async def create_meeting(
        self,
        unit_key: str,
        actor_id: UUID,
        input_data: CreateZoomMeetingInput,
        correlation_id: UUID,
    ) -> dict[str, object]:
        return {
            "meeting_id": "89360940442",
            "join_url": "https://zoom.us/j/1",
            "passcode": "123456",
        }

    async def list_meetings(
        self, unit_key: str, actor_id: UUID, input_data: ListZoomMeetingsInput
    ) -> dict[str, object]:
        return {"items": []}

    async def get_meeting(
        self, unit_key: str, actor_id: UUID, input_data: GetZoomMeetingInput
    ) -> dict[str, object]:
        return {"meeting_id": input_data.meeting_id, "topic": "Test"}


class DummyPolicy:
    checks: ClassVar[list[CheckRequest]] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(allowed=True, model_id="test")

    async def list_authorized_objects(self, request: object) -> tuple[str, ...]:
        return ()


class DummyToken:
    subject: ClassVar[str] = "user:0191c49b-7377-7890-a123-456789abcdef"
    client_id: ClassVar[str] = "test-client"
    scopes: ClassVar[frozenset[str]] = frozenset({"zoom:create", "zoom:read"})
    claims: ClassVar[dict[str, str]] = {"active_unit": "direction-systemes"}


@pytest.mark.asyncio
async def test_zoom_tools_registration_and_execution() -> None:
    DummyPolicy.checks.clear()
    server = MCPServer("test-registry")
    auth = AuthorizationService(DummyPolicy())
    guard = RegistryGuard(auth, access_token_provider=lambda: DummyToken())  # type: ignore[arg-type]
    audit = DummyAuditSink()
    backend = DummyZoomBackend()

    register_zoom_tools(server, backend=backend, guard=guard, audit=audit)

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert "prepare_zoom_meeting" in tool_names
    assert "create_zoom_meeting" in tool_names
    assert "list_zoom_meetings" in tool_names
    assert "get_zoom_meeting" in tool_names

    prep = await server.call_tool(
        "prepare_zoom_meeting",
        {
            "topic": "Comité Direction",
            "start_time": "2026-09-22T10:00:00",
            "duration_minutes": 60,
        },
    )
    assert prep.structured_content["plan_id"] == "plan-123"

    created = await server.call_tool(
        "create_zoom_meeting",
        {
            "plan_id": "plan-123",
            "idempotency_key": "idemp-meeting-test-12345",
        },
    )
    assert created.structured_content["meeting_id"] == "89360940442"

    meetings = await server.call_tool("list_zoom_meetings", {})
    assert meetings.structured_content == {"items": []}

    meeting = await server.call_tool("get_zoom_meeting", {"meeting_id": "89360940442"})
    assert meeting.structured_content["meeting_id"] == "89360940442"

    decisions = {(check.relation, check.object) for check in DummyPolicy.checks}
    assert ("can_view", "org_unit:direction-systemes") in decisions
    assert ("can_manage", "org_unit:direction-systemes") in decisions
