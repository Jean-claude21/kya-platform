"""Safe metadata for locating secrets through a dedicated provider."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SecretStatus(StrEnum):
    ACTIVE = "active"
    ROTATION_DUE = "rotation_due"
    REVOKED = "revoked"


class SecretReference(BaseModel):
    """Opaque locator and governance metadata; never a credential value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    locator: str = Field(min_length=1, max_length=512)
    key_name: str = Field(min_length=1, max_length=128)
    owner_scope: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=255)
    environment: str = Field(pattern=r"^(local|preview|test|production)$")
    status: SecretStatus
    created_at: datetime
    rotated_at: datetime | None = None
    expires_at: datetime | None = None


__all__ = ["SecretReference", "SecretStatus"]
