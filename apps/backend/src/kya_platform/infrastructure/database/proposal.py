"""Transactional Neon adapter for non-developer capability proposals."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application import OutboxMessage
from kya_platform.application.proposal import ProposalRecord
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus
from kya_platform.infrastructure.database.models import CatalogProposal, OutboxEvent

_OPEN_STATUSES = (
    ProposalStatus.SUBMITTED.value,
    ProposalStatus.IN_REVIEW.value,
    ProposalStatus.APPROVED.value,
    ProposalStatus.PULL_REQUEST_OPEN.value,
)


def _domain(row: CatalogProposal) -> Proposal:
    return Proposal(
        id=row.id,
        target_workspace_id=row.target_workspace_id,
        slug=row.slug,
        artifact_type=ArtifactType(row.artifact_type),
        artifact_id=row.artifact_id,
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        status=ProposalStatus(row.status),
        reviewer_id=row.reviewer_id,
        review_reason=row.review_reason,
        reviewed_at=row.reviewed_at,
        pull_request_url=row.pull_request_url,
        merged_commit_sha=row.merged_commit_sha,
        resulting_artifact_version_id=row.resulting_artifact_version_id,
    )


class SqlAlchemyProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, proposal_id: UUID) -> ProposalRecord | None:
        row = await self._session.scalar(
            select(CatalogProposal).where(CatalogProposal.id == proposal_id).with_for_update()
        )
        if row is None:
            return None
        return ProposalRecord(
            proposal=_domain(row), package=ProposalPackage.model_validate(row.package)
        )

    async def count_open_for_author(self, author_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(CatalogProposal)
            .where(
                CatalogProposal.requested_by == author_id,
                CatalogProposal.status.in_(_OPEN_STATUSES),
            )
        )
        return int(count or 0)

    async def save(self, proposal: Proposal, *, package: ProposalPackage) -> None:
        row = await self._session.scalar(
            select(CatalogProposal).where(CatalogProposal.id == proposal.id).with_for_update()
        )
        payload = package.model_dump(mode="json", by_alias=True, exclude_none=True)
        if row is None:
            self._session.add(
                CatalogProposal(
                    id=proposal.id,
                    artifact_id=proposal.artifact_id,
                    target_workspace_id=proposal.target_workspace_id,
                    slug=proposal.slug,
                    artifact_type=proposal.artifact_type.value,
                    package=payload,
                    requested_by=proposal.requested_by,
                    requested_at=proposal.requested_at,
                    status=proposal.status.value,
                )
            )
            return
        row.status = proposal.status.value
        row.reviewer_id = proposal.reviewer_id
        if proposal.status is ProposalStatus.APPROVED:
            row.review_decision = "approved"
        elif proposal.status is ProposalStatus.REJECTED:
            row.review_decision = "rejected"
        row.review_reason = proposal.review_reason
        row.reviewed_at = proposal.reviewed_at
        row.pull_request_url = proposal.pull_request_url
        row.merged_commit_sha = proposal.merged_commit_sha
        row.resulting_artifact_version_id = proposal.resulting_artifact_version_id
        row.package = payload


class SqlAlchemyProposalOutbox:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: OutboxMessage) -> None:
        self._session.add(
            OutboxEvent(
                topic=message.topic,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                payload=dict(message.payload),
                correlation_id=message.correlation_id,
            )
        )


class SqlAlchemyProposalUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None
        self.proposals: SqlAlchemyProposalRepository
        self.outbox: SqlAlchemyProposalOutbox

    async def __aenter__(self) -> SqlAlchemyProposalUnitOfWork:
        self._session = self._sessions()
        await self._session.begin()
        self.proposals = SqlAlchemyProposalRepository(self._session)
        self.outbox = SqlAlchemyProposalOutbox(self._session)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        del exc_type, exc_value, traceback
        if self._session is not None:
            if self._session.in_transaction():
                await self._session.rollback()
            await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("proposal unit of work is not active")
        await self._session.commit()


__all__ = [
    "SqlAlchemyProposalOutbox",
    "SqlAlchemyProposalRepository",
    "SqlAlchemyProposalUnitOfWork",
]
