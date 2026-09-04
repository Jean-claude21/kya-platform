"""Publication use cases persist decisions and external effects atomically."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.publication import (
    PublicationNotFoundError,
    PublicationService,
    PublicationUnitOfWorkFactory,
)
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    PublicationStatus,
    ReviewDecision,
)

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
APPROVER = UUID("019914b2-1a40-7000-8000-000000000033")
PUBLISHER = UUID("019914b2-1a40-7000-8000-000000000034")
REQUEST = UUID("019914b2-1a40-7000-8000-0000000000b1")
CORRELATION = UUID("019914b2-1a40-7000-8000-0000000000c1")
NOW = datetime(2026, 9, 4, tzinfo=UTC)


def version() -> ArtifactVersion:
    return ArtifactVersion(
        UUID("019914b2-1a40-7000-8000-0000000000a1"),
        "1.0.0",
        "a" * 40,
        "b" * 64,
        "c" * 64,
    )


class FakePublications:
    def __init__(self) -> None:
        self.record: PublicationRequest | None = None

    async def get(self, request_id: UUID) -> PublicationRequest | None:
        return self.record if self.record and self.record.id == request_id else None

    async def save(self, request: PublicationRequest) -> None:
        self.record = request


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.publications = FakePublications()
        self.outbox = FakeOutbox()
        self.commits = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_publication_keeps_one_digest_and_emits_transactional_events() -> None:
    unit_of_work = FakeUnitOfWork()
    service = PublicationService(
        cast(PublicationUnitOfWorkFactory, lambda: unit_of_work)
    )

    await service.submit(
        request_id=REQUEST,
        candidate=version(),
        actor_id=AUTHOR,
        at=NOW,
        correlation_id=CORRELATION,
    )
    await service.review(
        REQUEST,
        actor_id=REVIEWER,
        decision=ReviewDecision.ACCEPTED,
        at=NOW,
        correlation_id=CORRELATION,
    )
    await service.approve(
        REQUEST,
        actor_id=APPROVER,
        decision=ApprovalDecision.APPROVED,
        at=NOW,
        correlation_id=CORRELATION,
    )
    published = await service.publish(
        REQUEST,
        actor_id=PUBLISHER,
        content_digest="b" * 64,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert published.status is PublicationStatus.PUBLISHED
    assert unit_of_work.commits == 4
    assert [message.topic for message in unit_of_work.outbox.messages] == [
        "publication.requested",
        "publication.reviewed",
        "publication.approved",
        "artifact.published",
    ]
    assert {message.payload["content_digest"] for message in unit_of_work.outbox.messages} == {
        "b" * 64
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_rejects_a_digest_substitution_without_commit_or_event() -> None:
    unit_of_work = FakeUnitOfWork()
    unit_of_work.publications.record = (
        PublicationRequest.open(
            id=REQUEST,
            candidate=version(),
            requested_by=AUTHOR,
            requested_at=NOW,
            separation_of_duties=True,
        )
        .review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        .approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
    )
    service = PublicationService(
        cast(PublicationUnitOfWorkFactory, lambda: unit_of_work)
    )

    with pytest.raises(ValueError, match="digest differs"):
        await service.publish(
            REQUEST,
            actor_id=PUBLISHER,
            content_digest="d" * 64,
            at=NOW,
            correlation_id=CORRELATION,
        )

    assert unit_of_work.commits == 0
    assert unit_of_work.outbox.messages == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_publication_request_fails_closed() -> None:
    service = PublicationService(
        cast(PublicationUnitOfWorkFactory, lambda: FakeUnitOfWork())
    )

    with pytest.raises(PublicationNotFoundError):
        await service.review(
            REQUEST,
            actor_id=REVIEWER,
            decision=ReviewDecision.ACCEPTED,
            at=NOW,
            correlation_id=CORRELATION,
        )
