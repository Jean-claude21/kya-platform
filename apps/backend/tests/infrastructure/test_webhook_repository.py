"""Webhook subscription persistence stores routing metadata, never secret values."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from kya_platform.application.webhook_subscriptions import WebhookSubscription
from kya_platform.infrastructure.database.webhooks import (
    SqlAlchemyWebhookSubscriptionRepository,
)

SUBSCRIPTION_ID = UUID("11111111-1111-4111-8111-111111111111")
SECRET_ID = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 9, 18, tzinfo=UTC)


def row() -> SimpleNamespace:
    return SimpleNamespace(
        id=SUBSCRIPTION_ID,
        owner_scope="workspace:platform",
        endpoint_url="https://forms.kya.energy/hooks/platform",
        event_types=["com.kya.form.submitted.v1"],
        secret_reference_id=SECRET_ID,
        is_enabled=True,
        created_at=NOW,
    )


class Session:
    def __init__(self, existing: object | None) -> None:
        self.existing = existing
        self.added: list[object] = []
        self.commits = 0

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, _model: object, _identifier: UUID) -> object | None:
        return self.existing

    async def scalars(self, _statement: object) -> tuple[object, ...]:
        return (self.existing,) if self.existing is not None else ()

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


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


@pytest.mark.asyncio
async def test_get_and_list_rehydrate_only_secret_reference() -> None:
    session = Session(row())
    repository = SqlAlchemyWebhookSubscriptionRepository(Sessions(session))  # type: ignore[arg-type]

    found = await repository.get(SUBSCRIPTION_ID)
    listed = await repository.list_for_event("workspace:platform", "com.kya.form.submitted.v1")

    assert found == subscription()
    assert listed == (subscription(),)
    assert not hasattr(session.existing, "secret_value")


@pytest.mark.asyncio
async def test_save_inserts_then_updates_routing_metadata() -> None:
    insert_session = Session(None)
    insert_repository = SqlAlchemyWebhookSubscriptionRepository(  # type: ignore[arg-type]
        Sessions(insert_session)
    )

    await insert_repository.save(subscription())

    assert len(insert_session.added) == 1
    assert insert_session.commits == 1

    existing = row()
    update_session = Session(existing)
    update_repository = SqlAlchemyWebhookSubscriptionRepository(  # type: ignore[arg-type]
        Sessions(update_session)
    )

    await update_repository.save(subscription(enabled=False))

    assert existing.is_enabled is False
    assert update_session.added == []
    assert update_session.commits == 1
