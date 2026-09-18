"""Stable event envelope shared by KYA applications, webhooks and MCP projections."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class EventContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(alias="unitId", min_length=1, max_length=255)
    workspace_id: str | None = Field(default=None, alias="workspaceId", max_length=255)


class KyaEventEnvelope(BaseModel):
    """CloudEvents-shaped business event with explicit KYA governance context."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    spec_version: Literal["1.0"] = Field(default="1.0", alias="specversion")
    event_id: UUID = Field(alias="id")
    event_type: str = Field(
        alias="type",
        pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$",
        max_length=160,
    )
    source: AnyUrl
    subject: str = Field(min_length=1, max_length=255)
    occurred_at: datetime = Field(alias="time")
    data_content_type: Literal["application/json"] = Field(
        default="application/json", alias="datacontenttype"
    )
    schema_version: str = Field(default="1", alias="schemaVersion", min_length=1, max_length=32)
    context: EventContext
    correlation_id: UUID = Field(alias="correlationId")
    causation_id: UUID | None = Field(default=None, alias="causationId")
    actor_id: UUID | None = Field(default=None, alias="actorId")
    data: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event time must include a timezone")
        return value


__all__ = ["EventContext", "KyaEventEnvelope"]
