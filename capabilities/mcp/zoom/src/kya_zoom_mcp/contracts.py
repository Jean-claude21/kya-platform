"""Stable contracts exposed by the KYA-Zoom application service."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MeetingProfile(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    CONFIDENTIAL = "confidential"


class KyaContext(StrictModel):
    """Verified identity propagated by KYA-Platform, never supplied by tool arguments."""

    principal_id: str = Field(min_length=1)
    active_unit_id: str = Field(min_length=1)
    workspace_id: str | None = None
    correlation_id: UUID


class PrepareMeetingRequest(StrictModel):
    topic: str = Field(min_length=2, max_length=200)
    start_time: str = Field(min_length=10, max_length=50)
    duration_minutes: int = Field(ge=1, le=1_440)
    timezone: str = Field(default="Africa/Lome", min_length=1, max_length=100)
    profile: MeetingProfile = MeetingProfile.INTERNAL
    agenda: str | None = Field(default=None, max_length=2_000)


class MeetingSettings(StrictModel):
    waiting_room: bool
    join_before_host: bool
    mute_upon_entry: bool
    participant_video: bool
    auto_recording: str = Field(pattern=r"^(none|local|cloud)$")


class MeetingPlan(StrictModel):
    plan_id: UUID
    requested_by: str
    active_unit_id: str
    topic: str
    start_time: str
    timezone: str
    duration_minutes: int
    profile: MeetingProfile
    agenda: str | None
    settings: MeetingSettings
    expires_at: datetime
    required_permission: str = "zoom.meeting.create"
    confirmation_required: bool = True


class CreateMeetingRequest(StrictModel):
    plan_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")


class MeetingRecord(StrictModel):
    meeting_id: str = Field(min_length=1)
    topic: str
    start_time: str | None = None
    timezone: str | None = None
    duration_minutes: int | None = None
    status: str | None = None
    join_url: HttpUrl | None = None
    passcode: str | None = None


class CreateMeetingResult(StrictModel):
    operation_id: UUID
    idempotency_key: str
    meeting: MeetingRecord
    ready_to_share: bool


class MeetingList(StrictModel):
    items: list[MeetingRecord]
    next_page_token: str | None = None
