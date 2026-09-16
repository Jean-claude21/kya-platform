"""Channel preferences and an atomic ledger for idempotent notifications."""

import asyncio
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

_TOPIC_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9_-]*)+$")


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"


@dataclass(frozen=True, slots=True)
class NotificationPreference:
    recipient_id: UUID
    topic: str
    channel: NotificationChannel
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if not _TOPIC_PATTERN.fullmatch(self.topic):
            raise ValueError("notification topic must be explicit and namespaced")


class NotificationPreferencePort(Protocol):
    async def list_for(
        self, recipient_id: UUID, topic: str
    ) -> Sequence[NotificationPreference]: ...


class DeliveryLedgerPort(Protocol):
    async def begin(
        self,
        deduplication_key: str,
        channel: NotificationChannel,
        *,
        attempted_at: datetime,
    ) -> bool:
        """Reserve a delivery atomically; return false when already reserved or delivered."""

    async def complete(
        self,
        deduplication_key: str,
        channel: NotificationChannel,
        *,
        delivered_at: datetime,
    ) -> None: ...

    async def release(self, deduplication_key: str, channel: NotificationChannel) -> None: ...


class InMemoryNotificationPreferences:
    def __init__(self, preferences: Iterable[NotificationPreference] = ()) -> None:
        self._preferences = tuple(preferences)

    async def list_for(self, recipient_id: UUID, topic: str) -> tuple[NotificationPreference, ...]:
        return tuple(
            preference
            for preference in self._preferences
            if preference.recipient_id == recipient_id and preference.topic == topic
        )


class InMemoryDeliveryLedger:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, NotificationChannel], DeliveryStatus] = {}
        self._lock = asyncio.Lock()

    async def begin(
        self,
        deduplication_key: str,
        channel: NotificationChannel,
        *,
        attempted_at: datetime,
    ) -> bool:
        del attempted_at
        key = (deduplication_key, channel)
        async with self._lock:
            if key in self._entries:
                return False
            self._entries[key] = DeliveryStatus.PENDING
            return True

    async def complete(
        self,
        deduplication_key: str,
        channel: NotificationChannel,
        *,
        delivered_at: datetime,
    ) -> None:
        del delivered_at
        key = (deduplication_key, channel)
        async with self._lock:
            if self._entries.get(key) is not DeliveryStatus.PENDING:
                raise RuntimeError("notification delivery is not reserved")
            self._entries[key] = DeliveryStatus.DELIVERED

    async def release(self, deduplication_key: str, channel: NotificationChannel) -> None:
        key = (deduplication_key, channel)
        async with self._lock:
            if self._entries.get(key) is DeliveryStatus.PENDING:
                del self._entries[key]

    async def status(
        self, deduplication_key: str, channel: NotificationChannel
    ) -> DeliveryStatus | None:
        async with self._lock:
            return self._entries.get((deduplication_key, channel))


__all__ = [
    "DeliveryLedgerPort",
    "DeliveryStatus",
    "InMemoryDeliveryLedger",
    "InMemoryNotificationPreferences",
    "NotificationChannel",
    "NotificationPreference",
    "NotificationPreferencePort",
]
