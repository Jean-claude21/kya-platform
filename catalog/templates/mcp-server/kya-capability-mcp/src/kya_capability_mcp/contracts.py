"""Stable input and output contracts for the capability."""

from pydantic import BaseModel, ConfigDict, Field


class CapabilityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class CapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[CapabilityRecord]
    has_more: bool = False
