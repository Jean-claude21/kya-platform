"""Governed webhook subscriptions; signing values stay in the secret provider."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class WebhookSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    owner_scope: str = Field(min_length=1, max_length=255)
    endpoint_url: AnyHttpUrl
    event_types: tuple[str, ...] = Field(min_length=1, max_length=64)
    secret_reference_id: UUID
    is_enabled: bool = True
    created_at: datetime

    @field_validator("endpoint_url")
    @classmethod
    def require_https(cls, endpoint_url: AnyHttpUrl) -> AnyHttpUrl:
        if endpoint_url.scheme != "https":
            raise ValueError("webhook endpoint must use HTTPS")
        return endpoint_url

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, event_types: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(event_types))
        if normalized != event_types:
            raise ValueError("webhook event types must be unique")
        for event_type in event_types:
            parts = event_type.split(".")
            if len(parts) < 3 or any(not part.replace("-", "").isalnum() for part in parts):
                raise ValueError("webhook event type must be explicit and versioned")
        return event_types


class WebhookSubscriptionPort(Protocol):
    async def get(self, subscription_id: UUID) -> WebhookSubscription | None: ...

    async def list_for_event(
        self, owner_scope: str, event_type: str
    ) -> Sequence[WebhookSubscription]: ...

    async def save(self, subscription: WebhookSubscription) -> None: ...


class WebhookSecretResolverPort(Protocol):
    async def resolve(self, secret_reference_id: UUID) -> str: ...


class WebhookHttpPort(Protocol):
    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> None: ...


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    subscription_id: UUID
    event_id: UUID


__all__ = [
    "WebhookDelivery",
    "WebhookHttpPort",
    "WebhookSecretResolverPort",
    "WebhookSubscription",
    "WebhookSubscriptionPort",
]
