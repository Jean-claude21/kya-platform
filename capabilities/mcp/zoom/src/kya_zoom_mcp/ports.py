"""Infrastructure ports for policy, persistence, and Zoom."""

from __future__ import annotations

from typing import Protocol

from kya_zoom_mcp.contracts import (
    CreateMeetingResult,
    KyaContext,
    MeetingList,
    MeetingPlan,
    MeetingRecord,
)


class AuthorizationPort(Protocol):
    async def require(self, context: KyaContext, permission: str) -> None: ...


class MeetingPlanStore(Protocol):
    async def put(self, plan: MeetingPlan) -> None: ...

    async def get(self, plan_id: str) -> MeetingPlan | None: ...


class OperationStore(Protocol):
    async def get(self, principal_id: str, idempotency_key: str) -> CreateMeetingResult | None: ...

    async def put(
        self, principal_id: str, idempotency_key: str, result: CreateMeetingResult
    ) -> None: ...


class ZoomMeetingPort(Protocol):
    async def create_meeting(self, host_id: str, payload: dict[str, object]) -> MeetingRecord: ...

    async def list_meetings(
        self, host_id: str, *, page_size: int, next_page_token: str | None
    ) -> MeetingList: ...

    async def get_meeting(self, meeting_id: str) -> MeetingRecord: ...


class ZoomConnectionResolver(Protocol):
    """Resolve an authorized host without exposing provider credentials."""

    async def host_for(self, context: KyaContext) -> str: ...
