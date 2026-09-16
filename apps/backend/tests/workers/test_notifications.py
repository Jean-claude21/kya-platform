"""Notification delivery honours preferences and remains idempotent."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.notifications import (
    DeliveryStatus,
    InMemoryDeliveryLedger,
    InMemoryNotificationPreferences,
    NotificationChannel,
    NotificationPreference,
)
from kya_platform.workers.notifications import NotificationDeliveryWorker

NOW = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
ALICE = UUID("11111111-1111-4111-8111-111111111111")


class RecordingChannel:
    def __init__(self) -> None:
        self.deliveries: list[tuple[UUID, str, str, dict[str, str]]] = []

    async def deliver(
        self,
        *,
        recipient_id: UUID,
        template_id: str,
        locale: str,
        variables: dict[str, str],
    ) -> None:
        self.deliveries.append((recipient_id, template_id, locale, variables))


def payload(*, deduplication_key: str = "release:42:alice") -> dict[str, object]:
    return {
        "recipient_id": str(ALICE),
        "topic": "artifact.release.available",
        "deduplication_key": deduplication_key,
        "template_id": "artifact-release-available",
        "locale": "fr",
        "variables": {"artifact_name": "Skill Communication", "version": "1.2.0"},
    }


@pytest.mark.asyncio
async def test_delivers_only_on_enabled_preferred_channels() -> None:
    preferences = InMemoryNotificationPreferences(
        (
            NotificationPreference(ALICE, "artifact.release.available", NotificationChannel.IN_APP),
            NotificationPreference(
                ALICE,
                "artifact.release.available",
                NotificationChannel.EMAIL,
                is_enabled=False,
            ),
        )
    )
    in_app = RecordingChannel()
    email = RecordingChannel()
    ledger = InMemoryDeliveryLedger()
    worker = NotificationDeliveryWorker(
        preferences=preferences,
        ledger=ledger,
        channels={NotificationChannel.IN_APP: in_app, NotificationChannel.EMAIL: email},
        clock=lambda: NOW,
    )

    result = await worker.handle(payload())

    assert result.delivered == 1
    assert result.suppressed == 1
    assert result.duplicate == 0
    assert len(in_app.deliveries) == 1
    assert email.deliveries == []
    assert (
        await ledger.status("release:42:alice", NotificationChannel.IN_APP)
        is DeliveryStatus.DELIVERED
    )


@pytest.mark.asyncio
async def test_same_delivery_is_not_sent_twice() -> None:
    preferences = InMemoryNotificationPreferences(
        (NotificationPreference(ALICE, "artifact.release.available", NotificationChannel.IN_APP),)
    )
    channel = RecordingChannel()
    worker = NotificationDeliveryWorker(
        preferences=preferences,
        ledger=InMemoryDeliveryLedger(),
        channels={NotificationChannel.IN_APP: channel},
        clock=lambda: NOW,
    )

    first = await worker.handle(payload())
    second = await worker.handle(payload())

    assert first.delivered == 1
    assert second.duplicate == 1
    assert len(channel.deliveries) == 1


@pytest.mark.asyncio
async def test_failed_delivery_can_be_retried_by_outbox_runner() -> None:
    class FailingChannel(RecordingChannel):
        async def deliver(
            self,
            *,
            recipient_id: UUID,
            template_id: str,
            locale: str,
            variables: dict[str, str],
        ) -> None:
            raise TimeoutError("provider unavailable")

    preferences = InMemoryNotificationPreferences(
        (NotificationPreference(ALICE, "artifact.release.available", NotificationChannel.EMAIL),)
    )
    ledger = InMemoryDeliveryLedger()
    worker = NotificationDeliveryWorker(
        preferences=preferences,
        ledger=ledger,
        channels={NotificationChannel.EMAIL: FailingChannel()},
        clock=lambda: NOW,
    )

    with pytest.raises(TimeoutError, match="provider unavailable"):
        await worker.handle(payload())

    assert await ledger.status("release:42:alice", NotificationChannel.EMAIL) is None


@pytest.mark.asyncio
async def test_rejects_secret_shaped_template_variables() -> None:
    worker = NotificationDeliveryWorker(
        preferences=InMemoryNotificationPreferences(),
        ledger=InMemoryDeliveryLedger(),
        channels={},
        clock=lambda: NOW,
    )
    unsafe = payload()
    unsafe["variables"] = {"client_secret": "must-never-leave"}

    with pytest.raises(ValueError, match="sensitive variable"):
        await worker.handle(unsafe)


@pytest.mark.asyncio
async def test_concurrent_delivery_claim_has_one_winner() -> None:
    preferences = InMemoryNotificationPreferences(
        (NotificationPreference(ALICE, "artifact.release.available", NotificationChannel.IN_APP),)
    )
    channel = RecordingChannel()
    worker = NotificationDeliveryWorker(
        preferences=preferences,
        ledger=InMemoryDeliveryLedger(),
        channels={NotificationChannel.IN_APP: channel},
        clock=lambda: NOW,
    )

    results = await asyncio.gather(worker.handle(payload()), worker.handle(payload()))

    assert sum(result.delivered for result in results) == 1
    assert sum(result.duplicate for result in results) == 1
    assert len(channel.deliveries) == 1


@pytest.mark.asyncio
async def test_missing_enabled_channel_is_a_retryable_configuration_error() -> None:
    worker = NotificationDeliveryWorker(
        preferences=InMemoryNotificationPreferences(
            (
                NotificationPreference(
                    ALICE, "artifact.release.available", NotificationChannel.EMAIL
                ),
            )
        ),
        ledger=InMemoryDeliveryLedger(),
        channels={},
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="not configured"):
        await worker.dispatch(payload())


def test_preference_requires_specific_topic() -> None:
    with pytest.raises(ValueError, match="topic"):
        NotificationPreference(ALICE, "*", NotificationChannel.IN_APP)
