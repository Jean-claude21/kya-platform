"""Signed webhook deliveries are scoped, deterministic and secret-safe."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.webhook_subscriptions import WebhookSubscription
from kya_platform.contracts.events import KyaEventEnvelope
from kya_platform.workers.webhooks import WebhookDeliveryWorker

NOW = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
SUBSCRIPTION_ID = UUID("11111111-1111-4111-8111-111111111111")
SECRET_ID = UUID("22222222-2222-4222-8222-222222222222")
EVENT_ID = UUID("33333333-3333-4333-8333-333333333333")


class Subscriptions:
    def __init__(self, subscription: WebhookSubscription | None) -> None:
        self.subscription = subscription

    async def get(self, subscription_id: UUID) -> WebhookSubscription | None:
        assert subscription_id == SUBSCRIPTION_ID
        return self.subscription


class Secrets:
    def __init__(self) -> None:
        self.resolved: list[UUID] = []

    async def resolve(self, secret_reference_id: UUID) -> str:
        self.resolved.append(secret_reference_id)
        return "resolved-only-at-delivery"


class Http:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> None:
        self.calls.append((url, content, headers))


def subscription(*, enabled: bool = True) -> WebhookSubscription:
    return WebhookSubscription(
        id=SUBSCRIPTION_ID,
        owner_scope="workspace:platform",
        endpoint_url="https://forms.kya.energy/hooks/platform",
        event_types=("com.kya.form.submitted.v1",),
        secret_reference_id=SECRET_ID,
        is_enabled=enabled,
        created_at=NOW,
    )


def event() -> KyaEventEnvelope:
    return KyaEventEnvelope.model_validate(
        {
            "id": str(EVENT_ID),
            "source": "kya://forms",
            "type": "com.kya.form.submitted.v1",
            "time": NOW.isoformat(),
            "subject": "form:inspection-42",
            "context": {
                "unitId": "44444444-4444-4444-8444-444444444444",
                "workspaceId": "55555555-5555-4555-8555-555555555555",
            },
            "correlationId": "66666666-6666-4666-8666-666666666666",
            "data": {"record_id": "inspection-42"},
        }
    )


@pytest.mark.asyncio
async def test_delivers_signed_canonical_event() -> None:
    http = Http()
    secrets = Secrets()
    worker = WebhookDeliveryWorker(
        subscriptions=Subscriptions(subscription()),
        secrets=secrets,
        http=http,
        clock=lambda: NOW,
    )

    await worker.dispatch({"subscription_id": str(SUBSCRIPTION_ID), "event": event()})

    assert secrets.resolved == [SECRET_ID]
    assert len(http.calls) == 1
    url, body, headers = http.calls[0]
    assert url == "https://forms.kya.energy/hooks/platform"
    assert b'"record_id":"inspection-42"' in body
    assert headers["x-kya-event-id"] == str(EVENT_ID)
    assert headers["x-kya-signature"].startswith(f"t={int(NOW.timestamp())},v1=")
    assert "resolved-only-at-delivery" not in repr(http.calls)


@pytest.mark.asyncio
async def test_disabled_or_missing_subscription_is_safely_suppressed() -> None:
    http = Http()
    worker = WebhookDeliveryWorker(
        subscriptions=Subscriptions(subscription(enabled=False)),
        secrets=Secrets(),
        http=http,
        clock=lambda: NOW,
    )

    await worker.dispatch({"subscription_id": str(SUBSCRIPTION_ID), "event": event()})

    assert http.calls == []


@pytest.mark.asyncio
async def test_rejects_event_not_declared_by_subscription() -> None:
    http = Http()
    payload_event = event().model_copy(update={"event_type": "com.kya.workflow.approved.v1"})
    worker = WebhookDeliveryWorker(
        subscriptions=Subscriptions(subscription()),
        secrets=Secrets(),
        http=http,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="not allowed"):
        await worker.dispatch({"subscription_id": str(SUBSCRIPTION_ID), "event": payload_event})

    assert http.calls == []


def test_subscription_requires_https_and_versioned_unique_events() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        WebhookSubscription(
            id=SUBSCRIPTION_ID,
            owner_scope="workspace:platform",
            endpoint_url="http://unsafe.example",
            event_types=("com.kya.form.submitted.v1",),
            secret_reference_id=SECRET_ID,
            created_at=NOW,
        )

    with pytest.raises(ValueError, match="unique"):
        WebhookSubscription(
            id=SUBSCRIPTION_ID,
            owner_scope="workspace:platform",
            endpoint_url="https://forms.kya.energy/hooks/platform",
            event_types=("com.kya.form.submitted.v1", "com.kya.form.submitted.v1"),
            secret_reference_id=SECRET_ID,
            created_at=NOW,
        )
