"""Proposal routes enforce workspace/artifact permissions before any state change."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.proposal import ProposalRecord
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
BUSINESS_OWNER = UUID("019914b2-1a40-7000-8000-000000000041")
TECHNICAL_OWNER = UUID("019914b2-1a40-7000-8000-000000000042")
WORKSPACE = UUID("019914b2-1a40-7000-8000-000000000071")
PROPOSAL = UUID("019914b2-1a40-7000-8000-0000000000c1")
NOW = datetime(2026, 9, 11, tzinfo=UTC)


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "author", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return AUTHOR


class Policy:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


def opened_proposal() -> Proposal:
    return Proposal.open(
        id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-brief",
        artifact_type=ArtifactType.SKILL,
        artifact_id=None,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


class ProposalCommands:
    def __init__(self) -> None:
        self.submissions: list[dict[str, object]] = []
        self.pull_request_repositories: list[str] = []
        self.record: Proposal | None = None

    async def submit(self, **values: object) -> Proposal:
        self.submissions.append(values)
        self.record = opened_proposal()
        return self.record

    async def get(self, proposal_id: UUID) -> Proposal:
        assert self.record is not None
        return self.record

    async def get_record(self, proposal_id: UUID) -> ProposalRecord:
        assert self.record is not None
        return ProposalRecord(
            proposal=self.record,
            package=ProposalPackage.model_validate(proposal_body()["package"]),
        )

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        *,
        status: ProposalStatus | None = None,
        limit: int = 50,
    ) -> tuple[ProposalRecord, ...]:
        del workspace_id, status, limit
        if self.record is None:
            return ()
        return (await self.get_record(self.record.id),)

    async def approve(self, proposal_id: UUID, **values: object) -> Proposal:
        assert self.record is not None
        self.record = self.record.approve(
            REVIEWER,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
        )
        return self.record

    async def open_pull_request(
        self,
        proposal_id: UUID,
        *,
        repository: str,
        correlation_id: UUID,
    ) -> Proposal:
        del proposal_id, correlation_id
        assert self.record is not None
        self.pull_request_repositories.append(repository)
        self.record = self.record.mark_pull_request_open(
            pull_request_url="https://github.com/Jean-claude21/kya-platform-proposals/pull/1"
        )
        return self.record


def configure(app: FastAPI, *, allowed: bool) -> tuple[TestClient, Policy, ProposalCommands]:
    policy = Policy(allowed)
    commands = ProposalCommands()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.proposal_service = commands
    app.state.proposal_repository = "Jean-claude21/kya-platform-proposals"
    return TestClient(app), policy, commands


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


def proposal_body() -> dict[str, object]:
    return {
        "target_workspace_id": str(WORKSPACE),
        "slug": "solar-brief",
        "artifact_type": "skill",
        "package": {
            "schemaVersion": "1",
            "files": [
                {
                    "path": "SKILL.md",
                    "kind": PackageFileKind.INSTRUCTION.value,
                    "contentBase64": "LS0tCm5hbWU6IHNvbGFyLWJyaWVmCi0tLQo=",
                }
            ],
        },
    }


@pytest.mark.integration
def test_authorized_member_submits_a_proposal_without_a_git_commit(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    with client:
        response = client.post(
            "/api/v1/proposals",
            headers=headers(),
            json=proposal_body(),
        )

    assert response.status_code == 201
    assert response.json()["status"] == ProposalStatus.SUBMITTED.value
    assert response.json()["merged_commit_sha"] is None
    assert policy.checks[0].relation == "can_propose"
    assert policy.checks[0].object == f"workspace:{WORKSPACE}"
    assert commands.submissions[0]["requested_by"] == AUTHOR


@pytest.mark.integration
def test_denied_submission_never_reaches_the_proposal_service(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=False)
    with client:
        response = client.post(
            "/api/v1/proposals",
            headers=headers(),
            json=proposal_body(),
        )

    assert response.status_code == 403
    assert commands.submissions == []


@pytest.mark.integration
def test_approval_assigns_ownership_the_author_never_inherits(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    commands.record = opened_proposal()
    with client:
        response = client.post(
            f"/api/v1/proposals/{PROPOSAL}/approvals",
            headers=headers(),
            json={
                "business_owner_id": str(BUSINESS_OWNER),
                "technical_owner_id": str(TECHNICAL_OWNER),
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == ProposalStatus.APPROVED.value
    assert policy.checks[0].relation == "can_manage"
    assert policy.checks[0].object == f"workspace:{WORKSPACE}"


@pytest.mark.integration
def test_get_status_requires_the_same_review_permission(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    commands.record = opened_proposal()
    with client:
        response = client.get(f"/api/v1/proposals/{PROPOSAL}", headers=headers())

    assert response.status_code == 200
    assert response.json()["id"] == str(PROPOSAL)
    assert policy.checks[0].relation == "can_manage"


@pytest.mark.integration
def test_reviewer_lists_workspace_queue_with_package_facts(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    commands.record = opened_proposal()
    with client:
        response = client.get(
            f"/api/v1/proposals?target_workspace_id={WORKSPACE}",
            headers=headers(),
        )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(PROPOSAL)
    assert item["file_count"] == 1
    assert item["package_size"] > 0
    assert policy.checks[0].relation == "can_manage"


@pytest.mark.integration
def test_reviewer_reads_files_and_deterministic_evidence(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    commands.record = opened_proposal()
    with client:
        response = client.get(f"/api/v1/proposals/{PROPOSAL}/review", headers=headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal"]["id"] == str(PROPOSAL)
    assert payload["files"][0]["path"] == "SKILL.md"
    assert payload["files"][0]["contentBase64"]
    assert payload["evidence"][0]["status"] == "passed"
    assert policy.checks[0].relation == "can_manage"


@pytest.mark.integration
def test_pull_request_uses_only_the_server_configured_repository(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=True)
    commands.record = opened_proposal().approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )
    with client:
        response = client.post(
            f"/api/v1/proposals/{PROPOSAL}/pull-request",
            headers=headers(),
            json={},
        )

    assert response.status_code == 200
    assert response.json()["status"] == ProposalStatus.PULL_REQUEST_OPEN.value
    assert commands.pull_request_repositories == ["Jean-claude21/kya-platform-proposals"]


@pytest.mark.integration
def test_unauthenticated_request_is_rejected(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/proposals", json=proposal_body())

    assert response.status_code == 401
