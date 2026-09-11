"""Non-developer contribution use cases: proposals that pre-date a Git commit.

A Proposal is never executed and never becomes a Git-backed artifact version by itself. Approval
opens a pull request through a dedicated service identity; only a verified merge produces a real
`ArtifactVersion` eligible for the existing publication cycle (see `application.publication`).
"""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from kya_platform.application import OutboxMessage
from kya_platform.application.ports.reliability import OutboxPort
from kya_platform.contracts.artifact_package import ArtifactPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus

MAX_OPEN_PROPOSALS_PER_AUTHOR = 5


class ProposalNotFoundError(LookupError):
    """A proposal does not exist in the caller's disclosed scope."""


class ProposalQuotaExceededError(ValueError):
    """The author already has too many proposals awaiting review."""


@dataclass(frozen=True, slots=True)
class ProposalRecord:
    proposal: Proposal
    package: ArtifactPackage


class ProposalRepository(Protocol):
    async def get(self, proposal_id: UUID) -> ProposalRecord | None:
        """Load one proposal and its submitted package in the active transaction."""

    async def count_open_for_author(self, author_id: UUID) -> int:
        """Count proposals not yet in a terminal status for one author."""

    async def save(self, proposal: Proposal, *, package: ArtifactPackage) -> None:
        """Insert or update one proposal with its submitted package payload."""


class ProposalUnitOfWork(Protocol):
    proposals: ProposalRepository
    outbox: OutboxPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ProposalUnitOfWorkFactory(Protocol):
    def __call__(self) -> ProposalUnitOfWork: ...


class PullRequestPort(Protocol):
    """Narrow GitHub boundary: the service identity never holds standing merge rights."""

    async def open_pull_request(
        self,
        *,
        repository: str,
        slug: str,
        package: ArtifactPackage,
        required_approver_id: UUID,
        proposal_id: UUID,
    ) -> str:
        """Open a pull request on behalf of the service identity and return its URL."""

    async def get_merge_commit(self, pull_request_url: str) -> str | None:
        """Return the merge commit SHA once merged, or None while still open."""


class ProposalService:
    def __init__(
        self,
        unit_of_work_factory: ProposalUnitOfWorkFactory,
        pull_requests: PullRequestPort,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._pull_requests = pull_requests

    async def submit(
        self,
        *,
        proposal_id: UUID,
        target_workspace_id: UUID,
        slug: str,
        artifact_type: ArtifactType,
        artifact_id: UUID | None,
        package: ArtifactPackage,
        requested_by: UUID,
        at: datetime,
        correlation_id: UUID,
    ) -> Proposal:
        proposal = Proposal.open(
            id=proposal_id,
            target_workspace_id=target_workspace_id,
            slug=slug,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            requested_by=requested_by,
            requested_at=at,
        )
        async with self._unit_of_work_factory() as unit_of_work:
            open_count = await unit_of_work.proposals.count_open_for_author(requested_by)
            if open_count >= MAX_OPEN_PROPOSALS_PER_AUTHOR:
                raise ProposalQuotaExceededError(
                    f"at most {MAX_OPEN_PROPOSALS_PER_AUTHOR} open proposals are allowed per author"
                )
            await unit_of_work.proposals.save(proposal, package=package)
            await unit_of_work.outbox.add(
                self._event("proposal.submitted", proposal, correlation_id)
            )
            await unit_of_work.commit()
        return proposal

    async def approve(
        self,
        proposal_id: UUID,
        *,
        reviewer_id: UUID,
        business_owner_id: UUID,
        technical_owner_id: UUID,
        at: datetime,
        correlation_id: UUID,
    ) -> Proposal:
        async with self._unit_of_work_factory() as unit_of_work:
            record = await self._required(unit_of_work.proposals, proposal_id)
            approved = record.proposal.approve(
                reviewer_id,
                business_owner_id=business_owner_id,
                technical_owner_id=technical_owner_id,
                at=at,
            )
            await unit_of_work.proposals.save(approved, package=record.package)
            await unit_of_work.outbox.add(
                self._event("proposal.approved", approved, correlation_id)
            )
            await unit_of_work.commit()
        return approved

    async def reject(
        self,
        proposal_id: UUID,
        *,
        reviewer_id: UUID,
        reason: str,
        at: datetime,
        correlation_id: UUID,
    ) -> Proposal:
        async with self._unit_of_work_factory() as unit_of_work:
            record = await self._required(unit_of_work.proposals, proposal_id)
            rejected = record.proposal.reject(reviewer_id, reason=reason, at=at)
            await unit_of_work.proposals.save(rejected, package=record.package)
            await unit_of_work.outbox.add(
                self._event("proposal.rejected", rejected, correlation_id)
            )
            await unit_of_work.commit()
        return rejected

    async def open_pull_request(
        self, proposal_id: UUID, *, repository: str, correlation_id: UUID
    ) -> Proposal:
        async with self._unit_of_work_factory() as unit_of_work:
            record = await self._required(unit_of_work.proposals, proposal_id)
            pull_request_url = await self._pull_requests.open_pull_request(
                repository=repository,
                slug=record.proposal.slug,
                package=record.package,
                required_approver_id=record.proposal.reviewer_id or record.proposal.requested_by,
                proposal_id=proposal_id,
            )
            updated = record.proposal.mark_pull_request_open(pull_request_url=pull_request_url)
            await unit_of_work.proposals.save(updated, package=record.package)
            await unit_of_work.outbox.add(
                self._event("proposal.pull_request_opened", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    async def poll_merge_status(self, proposal_id: UUID, *, correlation_id: UUID) -> Proposal:
        """Check the linked pull request; never trusts a merge commit from client input."""

        async with self._unit_of_work_factory() as unit_of_work:
            record = await self._required(unit_of_work.proposals, proposal_id)
            if record.proposal.status is not ProposalStatus.PULL_REQUEST_OPEN:
                return record.proposal
            assert record.proposal.pull_request_url is not None
            commit_sha = await self._pull_requests.get_merge_commit(
                record.proposal.pull_request_url
            )
            if commit_sha is None:
                return record.proposal
            updated = record.proposal.mark_merged(
                commit_sha=commit_sha,
                resulting_artifact_version_id=proposal_id,
            )
            await unit_of_work.proposals.save(updated, package=record.package)
            await unit_of_work.outbox.add(self._event("proposal.merged", updated, correlation_id))
            await unit_of_work.commit()
        return updated

    @staticmethod
    async def _required(repository: ProposalRepository, proposal_id: UUID) -> ProposalRecord:
        record = await repository.get(proposal_id)
        if record is None:
            raise ProposalNotFoundError("proposal not found")
        return record

    @staticmethod
    def _event(topic: str, proposal: Proposal, correlation_id: UUID) -> OutboxMessage:
        return OutboxMessage(
            topic=topic,
            aggregate_type="proposal",
            aggregate_id=str(proposal.id),
            payload={
                "slug": proposal.slug,
                "artifact_type": proposal.artifact_type.value,
                "target_workspace_id": str(proposal.target_workspace_id),
                "status": proposal.status.value,
            },
            correlation_id=correlation_id,
        )


__all__ = [
    "MAX_OPEN_PROPOSALS_PER_AUTHOR",
    "ProposalNotFoundError",
    "ProposalQuotaExceededError",
    "ProposalRecord",
    "ProposalRepository",
    "ProposalService",
    "ProposalUnitOfWork",
    "ProposalUnitOfWorkFactory",
    "PullRequestPort",
]
