"""Neon scope promotion adapter widens the artifact's live scope once applied."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ReviewDecision,
    ScopePromotionRequest,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogScopePromotion,
    OutboxEvent,
)
from kya_platform.infrastructure.database.scope_promotion import (
    SqlAlchemyScopePromotionOutbox,
    SqlAlchemyScopePromotionRepository,
    SqlAlchemyScopePromotionUnitOfWork,
)

ARTIFACT = UUID("01991d00-0000-7000-8000-000000000401")
TEAM_UNIT = UUID("01991d00-0000-7000-8000-000000000402")
GROUP_UNIT = UUID("01991d00-0000-7000-8000-000000000403")
AUTHOR = UUID("01991d00-0000-7000-8000-000000000404")
REVIEWER = UUID("01991d00-0000-7000-8000-000000000405")
APPROVER = UUID("01991d00-0000-7000-8000-000000000406")
REQUEST_ID = UUID("01991d00-0000-7000-8000-000000000407")
CORRELATION = UUID("01991d00-0000-7000-8000-000000000408")
NOW = datetime(2026, 9, 12, tzinfo=UTC)


def opened() -> ScopePromotionRequest:
    return ScopePromotionRequest.open(
        id=REQUEST_ID,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


def applied_request() -> ScopePromotionRequest:
    return (
        opened()
        .review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        .approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
        .apply(APPROVER, at=NOW)
    )


def promotion_row(*, status: str = "awaiting-review") -> CatalogScopePromotion:
    return CatalogScopePromotion(
        id=REQUEST_ID,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
        requested_at=NOW,
        status=status,
    )


def artifact_row() -> CatalogArtifact:
    return CatalogArtifact(
        id=ARTIFACT,
        registry_id="kya",
        slug="document-standard",
        artifact_type="skill",
        name="Standard documentaire KYA",
        owner_workspace_id=ARTIFACT,
        business_owner_id=ARTIFACT,
        technical_owner_id=ARTIFACT,
        visibility="private",
        lifecycle="approved",
        visibility_scope_unit_id=TEAM_UNIT,
    )


class Session:
    def __init__(self, *, scalar_values: list[object] | None = None) -> None:
        self.scalar_values = scalar_values or []
        self.get_values: dict[tuple[type[object], UUID], object] = {}
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self.active = False

    async def scalar(self, statement: object) -> object:
        del statement
        return self.scalar_values.pop(0)

    async def get(self, model: type[object], identifier: UUID) -> object | None:
        return self.get_values.get((model, identifier))

    def add(self, row: object) -> None:
        self.added.append(row)

    async def begin(self) -> None:
        self.active = True

    def in_transaction(self) -> bool:
        return self.active

    async def commit(self) -> None:
        self.commits += 1
        self.active = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.active = False

    async def close(self) -> None:
        self.closed += 1


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_save_inserts_a_new_promotion_row() -> None:
    session = Session(scalar_values=[None])
    repository = SqlAlchemyScopePromotionRepository(session)  # type: ignore[arg-type]

    await repository.save(opened())

    row = next(item for item in session.added if isinstance(item, CatalogScopePromotion))
    assert row.status == "awaiting-review"


@pytest.mark.asyncio
async def test_get_reconstructs_the_promotion_request() -> None:
    session = Session(scalar_values=[promotion_row()])
    repository = SqlAlchemyScopePromotionRepository(session)  # type: ignore[arg-type]

    request = await repository.get(REQUEST_ID)

    assert request is not None
    assert request.current_scope_unit_id == TEAM_UNIT
    assert request.target_scope_unit_id == GROUP_UNIT


@pytest.mark.asyncio
async def test_applying_a_promotion_widens_the_artifact_scope_exactly_once() -> None:
    row = promotion_row(status="approved")
    artifact = artifact_row()
    session = Session(scalar_values=[row])
    session.get_values[(CatalogArtifact, ARTIFACT)] = artifact
    repository = SqlAlchemyScopePromotionRepository(session)  # type: ignore[arg-type]

    await repository.save(applied_request())

    assert row.status == "applied"
    assert artifact.visibility_scope_unit_id == GROUP_UNIT


@pytest.mark.asyncio
async def test_saving_an_already_applied_promotion_does_not_widen_again() -> None:
    row = promotion_row(status="applied")
    artifact = artifact_row()
    artifact.visibility_scope_unit_id = GROUP_UNIT
    session = Session(scalar_values=[row])
    session.get_values[(CatalogArtifact, ARTIFACT)] = artifact
    repository = SqlAlchemyScopePromotionRepository(session)  # type: ignore[arg-type]

    await repository.save(applied_request())

    assert artifact.visibility_scope_unit_id == GROUP_UNIT


@pytest.mark.asyncio
async def test_outbox_and_unit_of_work_share_the_same_transaction() -> None:
    session = Session()
    outbox = SqlAlchemyScopePromotionOutbox(session)  # type: ignore[arg-type]
    await outbox.add(
        OutboxMessage(
            "scope_promotion.requested", "scope_promotion", str(REQUEST_ID), {}, CORRELATION
        )
    )
    assert isinstance(session.added[0], OutboxEvent)

    unit = SqlAlchemyScopePromotionUnitOfWork(Sessions(session))  # type: ignore[arg-type]
    async with unit:
        await unit.commit()

    assert session.commits == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_when_left_without_commit() -> None:
    session = Session()
    unit = SqlAlchemyScopePromotionUnitOfWork(Sessions(session))  # type: ignore[arg-type]

    async with unit:
        pass

    assert session.rollbacks == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rejects_commit_before_entry() -> None:
    unit = SqlAlchemyScopePromotionUnitOfWork(Sessions(Session()))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="not active"):
        await unit.commit()
