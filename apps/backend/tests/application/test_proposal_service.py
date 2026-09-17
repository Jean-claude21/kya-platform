"""Proposal use cases: a non-developer contribution never bypasses human review."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.artifact_registry.proposal_validation import (
    ProposalValidationError,
)
from kya_platform.application.proposal import (
    ProposalNotFoundError,
    ProposalQuotaExceededError,
    ProposalRecord,
    ProposalService,
    ProposalUnitOfWorkFactory,
)
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
BUSINESS_OWNER = UUID("019914b2-1a40-7000-8000-000000000041")
TECHNICAL_OWNER = UUID("019914b2-1a40-7000-8000-000000000042")
WORKSPACE = UUID("019914b2-1a40-7000-8000-000000000071")
PROPOSAL = UUID("019914b2-1a40-7000-8000-0000000000c1")
CORRELATION = UUID("019914b2-1a40-7000-8000-0000000000c2")
NOW = datetime(2026, 9, 11, tzinfo=UTC)


def package() -> ProposalPackage:
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                content_base64="e30=",
            ),
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                content_base64="LS0tCm5hbWU6IHNvbGFyLWJyaWVmCi0tLQo=",
            ),
        ]
    )


def app_package() -> ProposalPackage:
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                content_base64="e30=",
            ),
            ProposalFile(
                path="package.json",
                kind=PackageFileKind.METADATA,
                content_base64="e30=",
            ),
        ]
    )


def mcp_package() -> ProposalPackage:
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                content_base64="e30=",
            ),
            ProposalFile(
                path="capability.manifest.json",
                kind=PackageFileKind.MANIFEST,
                content_base64="e30=",
            ),
            ProposalFile(
                path="pyproject.toml",
                kind=PackageFileKind.METADATA,
                content_base64="W3Byb2plY3RdCm5hbWUgPSAia3lhLW1jcC10ZXN0Igo=",
            ),
        ]
    )


class FakeProposals:
    def __init__(self) -> None:
        self.records: dict[UUID, ProposalRecord] = {}
        self.open_counts: dict[UUID, int] = {}

    async def get(self, proposal_id: UUID) -> ProposalRecord | None:
        return self.records.get(proposal_id)

    async def count_open_for_author(self, author_id: UUID) -> int:
        return self.open_counts.get(author_id, 0)

    async def save(self, proposal: Proposal, *, package: ProposalPackage) -> None:
        self.records[proposal.id] = ProposalRecord(proposal=proposal, package=package)


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class FakeUnitOfWork:
    def __init__(self, proposals: FakeProposals) -> None:
        self.proposals = proposals
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


class FakePullRequests:
    def __init__(self, *, merge_commit: str | None = None) -> None:
        self.opened: list[UUID] = []
        self._merge_commit = merge_commit

    async def open_pull_request(
        self,
        *,
        repository: str,
        slug: str,
        artifact_type: ArtifactType,
        package: ProposalPackage,
        required_approver_id: UUID,
        proposal_id: UUID,
    ) -> str:
        self.opened.append(proposal_id)
        return "https://github.com/kya/kya-platform/pull/1"

    async def get_merge_commit(self, pull_request_url: str) -> str | None:
        return self._merge_commit


def build_service(
    proposals: FakeProposals, pull_requests: FakePullRequests
) -> tuple[ProposalService, FakeUnitOfWork]:
    unit_of_work = FakeUnitOfWork(proposals)
    service = ProposalService(cast(ProposalUnitOfWorkFactory, lambda: unit_of_work), pull_requests)
    return service, unit_of_work


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_requires_no_git_commit_and_emits_one_event() -> None:
    proposals = FakeProposals()
    service, unit_of_work = build_service(proposals, FakePullRequests())

    proposal = await service.submit(
        proposal_id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-brief",
        artifact_type=ArtifactType.SKILL,
        artifact_id=None,
        package=package(),
        requested_by=AUTHOR,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert proposal.status is ProposalStatus.SUBMITTED
    assert proposal.merged_commit_sha is None
    assert unit_of_work.commits == 1
    assert [message.topic for message in unit_of_work.outbox.messages] == ["proposal.submitted"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_application_submission_uses_the_same_governed_proposal_path() -> None:
    proposals = FakeProposals()
    service, unit_of_work = build_service(proposals, FakePullRequests())

    proposal = await service.submit(
        proposal_id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-operations",
        artifact_type=ArtifactType.APPLICATION,
        artifact_id=None,
        package=app_package(),
        requested_by=AUTHOR,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert proposal.artifact_type is ArtifactType.APPLICATION
    assert proposal.status is ProposalStatus.SUBMITTED
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mcp_submission_uses_the_same_governed_proposal_path() -> None:
    proposals = FakeProposals()
    service, unit_of_work = build_service(proposals, FakePullRequests())

    proposal = await service.submit(
        proposal_id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-operations-mcp",
        artifact_type=ArtifactType.MCP_SERVER,
        artifact_id=None,
        package=mcp_package(),
        requested_by=AUTHOR,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert proposal.artifact_type is ArtifactType.MCP_SERVER
    assert proposal.status is ProposalStatus.SUBMITTED
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_is_idempotent_for_the_same_proposal_identifier() -> None:
    proposals = FakeProposals()
    service, unit_of_work = build_service(proposals, FakePullRequests())
    values = {
        "proposal_id": PROPOSAL,
        "target_workspace_id": WORKSPACE,
        "slug": "solar-brief",
        "artifact_type": ArtifactType.SKILL,
        "artifact_id": None,
        "package": package(),
        "requested_by": AUTHOR,
        "at": NOW,
        "correlation_id": CORRELATION,
    }

    first = await service.submit(**values)
    second = await service.submit(**values)

    assert second == first
    assert unit_of_work.commits == 1
    assert [message.topic for message in unit_of_work.outbox.messages] == ["proposal.submitted"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_submission_rejects_a_secret_before_any_reviewer_sees_it() -> None:
    proposals = FakeProposals()
    service, unit_of_work = build_service(proposals, FakePullRequests())
    unsafe = ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                content_base64="e30=",
            ),
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                content_base64="c2stMTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2",
            ),
        ]
    )

    with pytest.raises(ProposalValidationError, match="secret"):
        await service.submit(
            proposal_id=PROPOSAL,
            target_workspace_id=WORKSPACE,
            slug="solar-brief",
            artifact_type=ArtifactType.SKILL,
            artifact_id=None,
            package=unsafe,
            requested_by=AUTHOR,
            at=NOW,
            correlation_id=CORRELATION,
        )

    assert unit_of_work.commits == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_quota_fails_closed_once_the_author_has_five_open_proposals() -> None:
    proposals = FakeProposals()
    proposals.open_counts[AUTHOR] = 5
    service, unit_of_work = build_service(proposals, FakePullRequests())

    with pytest.raises(ProposalQuotaExceededError):
        await service.submit(
            proposal_id=PROPOSAL,
            target_workspace_id=WORKSPACE,
            slug="solar-brief",
            artifact_type=ArtifactType.SKILL,
            artifact_id=None,
            package=package(),
            requested_by=AUTHOR,
            at=NOW,
            correlation_id=CORRELATION,
        )

    assert unit_of_work.commits == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_approval_assigns_ownership_never_inherited_from_the_author() -> None:
    proposals = FakeProposals()
    proposals.records[PROPOSAL] = ProposalRecord(
        proposal=Proposal.open(
            id=PROPOSAL,
            target_workspace_id=WORKSPACE,
            slug="solar-brief",
            artifact_type=ArtifactType.SKILL,
            artifact_id=None,
            requested_by=AUTHOR,
            requested_at=NOW,
        ),
        package=package(),
    )
    service, unit_of_work = build_service(proposals, FakePullRequests())

    approved = await service.approve(
        PROPOSAL,
        reviewer_id=REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
        correlation_id=CORRELATION,
    )

    assert approved.business_owner_id == BUSINESS_OWNER
    assert approved.technical_owner_id == TECHNICAL_OWNER
    assert approved.requested_by == AUTHOR
    assert unit_of_work.outbox.messages[-1].topic == "proposal.approved"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_proposal_fails_closed() -> None:
    service, _ = build_service(FakeProposals(), FakePullRequests())

    with pytest.raises(ProposalNotFoundError):
        await service.approve(
            PROPOSAL,
            reviewer_id=REVIEWER,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
            correlation_id=CORRELATION,
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_opening_a_pull_request_records_its_url_and_uses_the_service_identity() -> None:
    proposals = FakeProposals()
    approved = Proposal.open(
        id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-brief",
        artifact_type=ArtifactType.SKILL,
        artifact_id=None,
        requested_by=AUTHOR,
        requested_at=NOW,
    ).approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )
    proposals.records[PROPOSAL] = ProposalRecord(proposal=approved, package=package())
    pull_requests = FakePullRequests()
    service, unit_of_work = build_service(proposals, pull_requests)

    opened = await service.open_pull_request(
        PROPOSAL, repository="kya-energy/kya-platform", correlation_id=CORRELATION
    )

    assert opened.status is ProposalStatus.PULL_REQUEST_OPEN
    assert opened.pull_request_url == "https://github.com/kya/kya-platform/pull/1"
    assert pull_requests.opened == [PROPOSAL]
    assert unit_of_work.outbox.messages[-1].topic == "proposal.pull_request_opened"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_polling_before_merge_leaves_the_proposal_unchanged() -> None:
    proposals = FakeProposals()
    pull_request_open = (
        Proposal.open(
            id=PROPOSAL,
            target_workspace_id=WORKSPACE,
            slug="solar-brief",
            artifact_type=ArtifactType.SKILL,
            artifact_id=None,
            requested_by=AUTHOR,
            requested_at=NOW,
        )
        .approve(
            REVIEWER,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
        )
        .mark_pull_request_open(pull_request_url="https://github.com/kya/kya-platform/pull/1")
    )
    proposals.records[PROPOSAL] = ProposalRecord(proposal=pull_request_open, package=package())
    service, unit_of_work = build_service(proposals, FakePullRequests(merge_commit=None))

    unchanged = await service.poll_merge_status(PROPOSAL, correlation_id=CORRELATION)

    assert unchanged.status is ProposalStatus.PULL_REQUEST_OPEN
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_polling_after_merge_never_trusts_a_client_supplied_commit() -> None:
    proposals = FakeProposals()
    pull_request_open = (
        Proposal.open(
            id=PROPOSAL,
            target_workspace_id=WORKSPACE,
            slug="solar-brief",
            artifact_type=ArtifactType.SKILL,
            artifact_id=None,
            requested_by=AUTHOR,
            requested_at=NOW,
        )
        .approve(
            REVIEWER,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
        )
        .mark_pull_request_open(pull_request_url="https://github.com/kya/kya-platform/pull/1")
    )
    proposals.records[PROPOSAL] = ProposalRecord(proposal=pull_request_open, package=package())
    merge_commit = "a" * 40
    service, unit_of_work = build_service(proposals, FakePullRequests(merge_commit=merge_commit))

    merged = await service.poll_merge_status(PROPOSAL, correlation_id=CORRELATION)

    assert merged.status is ProposalStatus.MERGED
    assert merged.merged_commit_sha == merge_commit
    assert unit_of_work.outbox.messages[-1].topic == "proposal.merged"
