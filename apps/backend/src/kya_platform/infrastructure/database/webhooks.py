"""Neon adapter for governed webhook subscriptions."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.webhook_subscriptions import WebhookSubscription
from kya_platform.infrastructure.database.models.webhooks import WebhookSubscriptionRow


def _subscription(row: WebhookSubscriptionRow) -> WebhookSubscription:
    return WebhookSubscription(
        id=row.id,
        owner_scope=row.owner_scope,
        endpoint_url=row.endpoint_url,
        event_types=tuple(row.event_types),
        secret_reference_id=row.secret_reference_id,
        is_enabled=row.is_enabled,
        created_at=row.created_at,
    )


class SqlAlchemyWebhookSubscriptionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, subscription_id: UUID) -> WebhookSubscription | None:
        async with self._sessions() as session:
            row = await session.get(WebhookSubscriptionRow, subscription_id)
            return _subscription(row) if row is not None else None

    async def list_for_event(
        self, owner_scope: str, event_type: str
    ) -> Sequence[WebhookSubscription]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(WebhookSubscriptionRow).where(
                    WebhookSubscriptionRow.owner_scope == owner_scope,
                    WebhookSubscriptionRow.is_enabled.is_(True),
                    WebhookSubscriptionRow.event_types.contains([event_type]),
                )
            )
            return tuple(_subscription(row) for row in rows)

    async def save(self, subscription: WebhookSubscription) -> None:
        async with self._sessions() as session:
            row = await session.get(WebhookSubscriptionRow, subscription.id)
            values = {
                "owner_scope": subscription.owner_scope,
                "endpoint_url": str(subscription.endpoint_url),
                "event_types": list(subscription.event_types),
                "secret_reference_id": subscription.secret_reference_id,
                "is_enabled": subscription.is_enabled,
            }
            if row is None:
                session.add(WebhookSubscriptionRow(id=subscription.id, **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            await session.commit()


__all__ = ["SqlAlchemyWebhookSubscriptionRepository"]
