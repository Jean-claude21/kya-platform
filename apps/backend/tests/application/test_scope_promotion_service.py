"""Scope promotion use cases: only ever widen visibility, never narrow it."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.scope_promotion import (
    ScopePromotionNotAncestorError,
    ScopePromotionNotFoundError,
    ScopePromotionService,
    ScopePromotionUnitOfWorkFactory,
)
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ReviewDecision,
    ScopePromotionRequest,
    ScopePromotionStatus,
)

ARTIFACT = UUID("019914b2-1a40-7000-8000-0000000000d1")
AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
APPROVER = UUID("019914b2-1a40-7000-8000-000000000033")
TEAM_UNIT = UUID("019914b2-1a40-7000-8000-0000000000e1")
GROUP_UNIT = UUID("019914b2-1a40-7000-8000-0000000000e2")
REQUEST = UUID("019914b2-1a40-7000-8000-0000000000f1")
CORRELATION = UUID("019914b2-1a40-7000-8000-0000000000f2")
NOW = datetime(2026, 9, 12, tzinfo=UTC)


class FakePromotions:
    def __init__(self) -> None:
        self.records: dict[UUID, ScopePromotionRequest] = {}

    async def get(self, request_id: UUID) -> ScopePromotionRequest | None:
        return self.records.get(request_id)

    async def save(self, request: ScopePromotionRequest) -> None:
        self.records[request.id] = request


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class FakeUnitOfWork:
    def __init__(self, promotions: FakePromotions) -> None:
        self.promotions = promotions
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


class FakeAuthorization:
    def __init__(self, *, ancestor: bool) -> None:
        self.ancestor = ancestor
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.ancestor, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return ()


def build_service(
    promotions: FakePromotions, *, ancestor: bool = True
) -> tuple[ScopePromotionService, FakeUnitOfWork, FakeAuthorization]:
    unit_of_work = FakeUnitOfWork(promotions)
    authorization = FakeAuthorization(ancestor=ancestor)
    service = ScopePromotionService(
        cast(ScopePromotionUnitOfWorkFactory, lambda: unit_of_work), authorization
    )
    return service, unit_of_work, authorization


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_requires_the_target_to_be_a_real_ancestor() -> None:
    service, unit_of_work, authorization = build_service(FakePromotions(), ancestor=False)

    with pytest.raises(ScopePromotionNotAncestorError):
        await service.submit(
            request_id=REQUEST,
            artifact_id=ARTIFACT,
            current_scope_unit_id=TEAM_UNIT,
            target_scope_unit_id=GROUP_UNIT,
            requested_by=AUTHOR,
            at=NOW,
            correlation_id=CORRELATION,
        )

    assert unit_of_work.commits == 0
    assert authorization.checks[0].relation == "ancestor"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_rejects_the_same_unit_as_current_and_target() -> None:
    service, unit_of_work, _authorization = build_service(FakePromotions())

    with pytest.raises(ValueError, match="different, wider unit"):
        await service.submit(
            request_id=REQUEST,
            artifact_id=ARTIFACT,
            current_scope_unit_id=TEAM_UNIT,
            target_scope_unit_id=TEAM_UNIT,
            requested_by=AUTHOR,
            at=NOW,
            correlation_id=CORRELATION,
        )

    assert unit_of_work.commits == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_succeeds_for_a_real_ancestor_and_emits_one_event() -> None:
    service, unit_of_work, _authorization = build_service(FakePromotions())

    promotion = await service.submit(
        request_id=REQUEST,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert promotion.status is ScopePromotionStatus.AWAITING_REVIEW
    assert unit_of_work.commits == 1
    assert [message.topic for message in unit_of_work.outbox.messages] == [
        "scope_promotion.requested"
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_promotion_reaches_applied_with_transactional_events() -> None:
    promotions = FakePromotions()
    service, unit_of_work, _authorization = build_service(promotions)

    await service.submit(
        request_id=REQUEST,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
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
    applied = await service.apply(REQUEST, actor_id=APPROVER, at=NOW, correlation_id=CORRELATION)

    assert applied.status is ScopePromotionStatus.APPLIED
    assert unit_of_work.commits == 4
    assert [message.topic for message in unit_of_work.outbox.messages] == [
        "scope_promotion.requested",
        "scope_promotion.reviewed",
        "scope_promotion.approved",
        "scope_promotion.applied",
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_promotion_fails_closed() -> None:
    service, _unit_of_work, _authorization = build_service(FakePromotions())

    with pytest.raises(ScopePromotionNotFoundError):
        await service.review(
            REQUEST,
            actor_id=REVIEWER,
            decision=ReviewDecision.ACCEPTED,
            at=NOW,
            correlation_id=CORRELATION,
        )
