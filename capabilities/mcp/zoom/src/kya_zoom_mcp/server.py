"""Thin MCP delivery layer with explicit runtime wiring."""

from __future__ import annotations

from typing import Annotated, Protocol

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from kya_zoom_mcp.contracts import (
    CreateMeetingRequest,
    KyaContext,
    MeetingProfile,
    PrepareMeetingRequest,
)
from kya_zoom_mcp.service import ZoomMeetingService

server = MCPServer(
    "KYA Zoom",
    instructions=(
        "Prepare Zoom meetings before creating them. Never expose a host start URL. "
        "All tools require a verified KYA identity and active organizational context."
    ),
)


class KyaContextProvider(Protocol):
    async def current(self, context: Context) -> KyaContext: ...


_service: ZoomMeetingService | None = None
_context_provider: KyaContextProvider | None = None


def configure_runtime(service: ZoomMeetingService, context_provider: KyaContextProvider) -> None:
    """Inject production adapters without weakening the tool contract."""

    global _context_provider, _service
    _service = service
    _context_provider = context_provider


def _runtime() -> tuple[ZoomMeetingService, KyaContextProvider]:
    if _service is None or _context_provider is None:
        raise RuntimeError(
            "KYA-Zoom runtime is not configured: verified KYA context "
            "and policy adapters are required"
        )
    return _service, _context_provider


@server.tool()
async def prepare_zoom_meeting(
    topic: Annotated[str, Field(min_length=2, max_length=200)],
    start_time: Annotated[str, Field(min_length=10, max_length=50)],
    duration_minutes: Annotated[int, Field(ge=1, le=1_440)],
    ctx: Context,
    timezone: str = "Africa/Lome",
    profile: MeetingProfile = MeetingProfile.INTERNAL,
    agenda: str | None = None,
) -> dict[str, object]:
    """Prepare a governed meeting preview. This does not create a Zoom meeting."""

    service, contexts = _runtime()
    kya_context = await contexts.current(ctx)
    result = await service.prepare(
        kya_context,
        PrepareMeetingRequest(
            topic=topic,
            start_time=start_time,
            duration_minutes=duration_minutes,
            timezone=timezone,
            profile=profile,
            agenda=agenda,
        ),
    )
    return result.model_dump(mode="json")


@server.tool()
async def create_zoom_meeting(
    plan_id: str,
    idempotency_key: Annotated[
        str,
        Field(min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
    ],
    ctx: Context,
) -> dict[str, object]:
    """Create one meeting from a confirmed plan; retries are idempotent."""

    service, contexts = _runtime()
    kya_context = await contexts.current(ctx)
    result = await service.create(
        kya_context,
        CreateMeetingRequest(plan_id=plan_id, idempotency_key=idempotency_key),
    )
    return result.model_dump(mode="json")


@server.tool()
async def list_zoom_meetings(
    ctx: Context,
    page_size: Annotated[int, Field(ge=1, le=100)] = 30,
    next_page_token: str | None = None,
) -> dict[str, object]:
    """List upcoming Zoom meetings authorized for the active KYA context."""

    service, contexts = _runtime()
    kya_context = await contexts.current(ctx)
    result = await service.list(
        kya_context,
        page_size=page_size,
        next_page_token=next_page_token,
    )
    return result.model_dump(mode="json")


@server.tool()
async def get_zoom_meeting(meeting_id: str, ctx: Context) -> dict[str, object]:
    """Get one safe meeting projection without a privileged host start URL."""

    service, contexts = _runtime()
    kya_context = await contexts.current(ctx)
    result = await service.get(kya_context, meeting_id)
    return result.model_dump(mode="json")


def main() -> None:
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
