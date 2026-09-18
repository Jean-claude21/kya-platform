"""Zoom MCP tool definitions and contracts for KYA Platform."""

from typing import Annotated

from pydantic import Field

from kya_platform.mcp.registry.contracts import (
    IdempotencyKey,
    RegistryRisk,
    RegistryTool,
    StrictMcpContract,
)

NonEmpty = Annotated[str, Field(min_length=1)]


class PrepareZoomMeetingInput(StrictMcpContract):
    topic: Annotated[str, Field(min_length=2, max_length=200)]
    start_time: Annotated[str, Field(min_length=10, max_length=50)]
    duration_minutes: Annotated[int, Field(ge=1, le=1_440)]
    timezone: str = Field(default="Africa/Lome", min_length=1, max_length=100)
    profile: str = Field(default="internal", pattern=r"^(internal|external|confidential)$")
    agenda: str | None = Field(default=None, max_length=2_000)


class CreateZoomMeetingInput(StrictMcpContract):
    plan_id: NonEmpty
    idempotency_key: IdempotencyKey


class ListZoomMeetingsInput(StrictMcpContract):
    page_size: Annotated[int, Field(ge=1, le=100)] = 30
    next_page_token: str | None = None


class GetZoomMeetingInput(StrictMcpContract):
    meeting_id: NonEmpty


ZOOM_TOOLS: tuple[RegistryTool, ...] = (
    RegistryTool(
        "prepare_zoom_meeting",
        "zoom:create",
        "can_view",
        "workspace",
        RegistryRisk.READ,
        is_write=False,
        requires_confirmation=False,
        requires_idempotency_key=False,
    ),
    RegistryTool(
        "create_zoom_meeting",
        "zoom:create",
        "can_edit",
        "workspace",
        RegistryRisk.CONTROLLED_WRITE,
        is_write=True,
        requires_confirmation=True,
        requires_idempotency_key=True,
    ),
    RegistryTool(
        "list_zoom_meetings",
        "zoom:read",
        "can_view",
        "workspace",
        RegistryRisk.READ,
        is_write=False,
        requires_confirmation=False,
        requires_idempotency_key=False,
    ),
    RegistryTool(
        "get_zoom_meeting",
        "zoom:read",
        "can_view",
        "workspace",
        RegistryRisk.READ,
        is_write=False,
        requires_confirmation=False,
        requires_idempotency_key=False,
    ),
)

__all__ = [
    "ZOOM_TOOLS",
    "CreateZoomMeetingInput",
    "GetZoomMeetingInput",
    "ListZoomMeetingsInput",
    "PrepareZoomMeetingInput",
]
