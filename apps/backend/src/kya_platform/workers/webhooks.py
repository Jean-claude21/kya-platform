"""Outbox-compatible signed webhook delivery."""

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from kya_platform.application.webhook_subscriptions import (
    WebhookHttpPort,
    WebhookSecretResolverPort,
    WebhookSubscriptionPort,
)
from kya_platform.application.webhooks import sign_webhook
from kya_platform.contracts.events import KyaEventEnvelope


class WebhookDeliveryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: UUID
    event: KyaEventEnvelope


class WebhookDeliveryWorker:
    def __init__(
        self,
        *,
        subscriptions: WebhookSubscriptionPort,
        secrets: WebhookSecretResolverPort,
        http: WebhookHttpPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._subscriptions = subscriptions
        self._secrets = secrets
        self._http = http
        self._clock = clock or (lambda: datetime.now(UTC))

    async def dispatch(self, raw_payload: Mapping[str, object]) -> None:
        payload = WebhookDeliveryPayload.model_validate(dict(raw_payload))
        subscription = await self._subscriptions.get(payload.subscription_id)
        if subscription is None or not subscription.is_enabled:
            return
        if payload.event.event_type not in subscription.event_types:
            raise ValueError("event is not allowed by the webhook subscription")

        body = json.dumps(
            payload.event.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        timestamp = int(self._clock().timestamp())
        secret = await self._secrets.resolve(subscription.secret_reference_id)
        signature = sign_webhook(body, secret.encode(), timestamp=timestamp)
        await self._http.post(
            str(subscription.endpoint_url),
            content=body,
            headers={
                "content-type": "application/cloudevents+json",
                "x-kya-event-id": str(payload.event.event_id),
                "x-kya-signature": signature.header_value,
                "x-kya-timestamp": str(signature.timestamp),
            },
        )


__all__ = ["WebhookDeliveryPayload", "WebhookDeliveryWorker"]
