"""Preference-aware, template-only notification delivery worker."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kya_platform.application.notifications import (
    DeliveryLedgerPort,
    NotificationChannel,
    NotificationPreferencePort,
)

_SENSITIVE_FRAGMENTS = (
    "api_key",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)


class NotificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_id: UUID
    topic: str = Field(pattern=r"^[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
    deduplication_key: str = Field(min_length=1, max_length=255)
    template_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    locale: str = Field(default="fr", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    variables: dict[str, str] = Field(default_factory=dict)

    @field_validator("variables")
    @classmethod
    def reject_sensitive_variables(cls, variables: dict[str, str]) -> dict[str, str]:
        if len(variables) > 32:
            raise ValueError("notification variables exceed the safe limit")
        for name, value in variables.items():
            normalized_name = name.casefold().replace("-", "_")
            if any(fragment in normalized_name for fragment in _SENSITIVE_FRAGMENTS):
                raise ValueError("notification contains a sensitive variable name")
            if not name or len(name) > 64 or len(value) > 512:
                raise ValueError("notification variable is outside safe limits")
        return variables


class NotificationChannelPort(Protocol):
    async def deliver(
        self,
        *,
        recipient_id: UUID,
        template_id: str,
        locale: str,
        variables: dict[str, str],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationDeliveryResult:
    delivered: int
    suppressed: int
    duplicate: int


class NotificationDeliveryWorker:
    """Deliver a trusted template once per recipient, event and channel."""

    def __init__(
        self,
        *,
        preferences: NotificationPreferencePort,
        ledger: DeliveryLedgerPort,
        channels: Mapping[NotificationChannel, NotificationChannelPort],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._preferences = preferences
        self._ledger = ledger
        self._channels = dict(channels)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, raw_payload: Mapping[str, object]) -> NotificationDeliveryResult:
        payload = NotificationPayload.model_validate(dict(raw_payload))
        preferences = await self._preferences.list_for(payload.recipient_id, payload.topic)
        delivered = suppressed = duplicate = 0

        for preference in preferences:
            if not preference.is_enabled:
                suppressed += 1
                continue
            channel = self._channels.get(preference.channel)
            if channel is None:
                raise RuntimeError(f"notification channel is not configured: {preference.channel}")
            reserved = await self._ledger.begin(
                payload.deduplication_key,
                preference.channel,
                attempted_at=self._clock(),
            )
            if not reserved:
                duplicate += 1
                continue
            try:
                await channel.deliver(
                    recipient_id=payload.recipient_id,
                    template_id=payload.template_id,
                    locale=payload.locale,
                    variables=dict(payload.variables),
                )
            except BaseException:
                await self._ledger.release(payload.deduplication_key, preference.channel)
                raise
            await self._ledger.complete(
                payload.deduplication_key,
                preference.channel,
                delivered_at=self._clock(),
            )
            delivered += 1

        return NotificationDeliveryResult(delivered, suppressed, duplicate)

    async def dispatch(self, raw_payload: Mapping[str, object]) -> None:
        """Adapt the notification worker to the generic outbox handler contract."""

        await self.handle(raw_payload)


__all__ = [
    "NotificationChannelPort",
    "NotificationDeliveryResult",
    "NotificationDeliveryWorker",
    "NotificationPayload",
]
