"""Neon proposal adapter keeps content, review decisions and outbox atomic."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus
from kya_platform.infrastructure.database.models import CatalogProposal, OutboxEvent
from kya_platform.infrastructure.database.proposal import (
    SqlAlchemyProposalOutbox,
    SqlAlchemyProposalRepository,
    SqlAlchemyProposalUnitOfWork,
)

PROPOSAL_ID = UUID("01991c00-0000-7000-8000-000000000201")
WORKSPACE_ID = UUID("01991c00-0000-7000-8000-000000000202")
AUTHOR = UUID("01991c00-0000-7000-8000-000000000203")
REVIEWER = UUID("01991c00-0000-7000-8000-000000000204")
BUSINESS_OWNER = UUID("01991c00-0000-7000-8000-000000000205")
TECHNICAL_OWNER = UUID("01991c00-0000-7000-8000-000000000206")
CORRELATION = UUID("01991c00-0000-7000-8000-000000000207")
NOW = datetime(2026, 9, 11, tzinfo=UTC)


def package() -> ProposalPackage:
    return ProposalPackage(
        files=[
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                content_base64="LS0tCm5hbWU6IHNvbGFyLWJyaWVmCi0tLQo=",
            )
        ]
    )


def opened_proposal() -> Proposal:
    return Proposal.open(
        id=PROPOSAL_ID,
        target_workspace_id=WORKSPACE_ID,
        slug="solar-brief",
        artifact_type=ArtifactType.SKILL,
        artifact_id=None,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


def proposal_row() -> CatalogProposal:
    return CatalogProposal(
        id=PROPOSAL_ID,
        artifact_id=None,
        target_workspace_id=WORKSPACE_ID,
        slug="solar-brief",
        artifact_type="skill",
        package=package().model_dump(mode="json", by_alias=True, exclude_none=True),
        requested_by=AUTHOR,
        requested_at=NOW,
        status="submitted",
    )


class Session:
    def __init__(self, scalars: list[object | None] | None = None) -> None:
        self.scalars = scalars or []
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self.active = False

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalars.pop(0)

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
async def test_get_returns_none_for_an_unknown_proposal() -> None:
    repository = SqlAlchemyProposalRepository(Session([None]))  # type: ignore[arg-type]

    assert await repository.get(PROPOSAL_ID) is None


@pytest.mark.asyncio
async def test_get_reconstructs_the_proposal_and_its_inline_package() -> None:
    repository = SqlAlchemyProposalRepository(Session([proposal_row()]))  # type: ignore[arg-type]

    record = await repository.get(PROPOSAL_ID)

    assert record is not None
    assert record.proposal.status is ProposalStatus.SUBMITTED
    assert record.package.files[0].path == "SKILL.md"


@pytest.mark.asyncio
async def test_count_open_for_author_reads_a_single_aggregate() -> None:
    repository = SqlAlchemyProposalRepository(Session([3]))  # type: ignore[arg-type]

    assert await repository.count_open_for_author(AUTHOR) == 3


@pytest.mark.asyncio
async def test_save_inserts_a_new_proposal_row() -> None:
    session = Session([None])
    repository = SqlAlchemyProposalRepository(session)  # type: ignore[arg-type]

    await repository.save(opened_proposal(), package=package())

    row = next(item for item in session.added if isinstance(item, CatalogProposal))
    assert row.id == PROPOSAL_ID
    assert row.status == "submitted"


@pytest.mark.asyncio
async def test_save_updates_an_existing_row_on_approval() -> None:
    row = proposal_row()
    session = Session([row])
    repository = SqlAlchemyProposalRepository(session)  # type: ignore[arg-type]
    approved = opened_proposal().approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )

    await repository.save(approved, package=package())

    assert row.status == "approved"
    assert row.review_decision == "approved"
    assert row.reviewer_id == REVIEWER
    assert session.added == []


@pytest.mark.asyncio
async def test_outbox_and_unit_of_work_share_the_same_transaction() -> None:
    session = Session()
    outbox = SqlAlchemyProposalOutbox(session)  # type: ignore[arg-type]
    await outbox.add(
        OutboxMessage("proposal.submitted", "proposal", str(PROPOSAL_ID), {}, CORRELATION)
    )
    assert isinstance(session.added[0], OutboxEvent)

    unit = SqlAlchemyProposalUnitOfWork(Sessions(session))  # type: ignore[arg-type]
    async with unit:
        await unit.commit()

    assert session.commits == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_when_left_without_commit() -> None:
    session = Session()
    unit = SqlAlchemyProposalUnitOfWork(Sessions(session))  # type: ignore[arg-type]

    async with unit:
        pass

    assert session.rollbacks == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rejects_commit_before_entry() -> None:
    unit = SqlAlchemyProposalUnitOfWork(Sessions(Session()))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="not active"):
        await unit.commit()
