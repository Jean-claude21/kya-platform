"""Scope promotion routes enforce artifact permissions before any widening."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity
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
NOW = datetime(2026, 9, 12, tzinfo=UTC)


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


def opened() -> ScopePromotionRequest:
    return ScopePromotionRequest.open(
        id=REQUEST,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


class ScopePromotionCommands:
    def __init__(self) -> None:
        self.submissions: list[dict[str, object]] = []
        self.record: ScopePromotionRequest | None = None

    async def submit(self, **values: object) -> ScopePromotionRequest:
        self.submissions.append(values)
        self.record = opened()
        return self.record

    async def review(self, request_id: UUID, **values: object) -> ScopePromotionRequest:
        assert self.record is not None
        self.record = self.record.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        return self.record

    async def approve(self, request_id: UUID, **values: object) -> ScopePromotionRequest:
        assert self.record is not None
        self.record = self.record.approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
        return self.record

    async def apply(self, request_id: UUID, **values: object) -> ScopePromotionRequest:
        assert self.record is not None
        self.record = self.record.apply(APPROVER, at=NOW)
        return self.record


def configure(app: FastAPI, *, allowed: bool) -> tuple[TestClient, Policy, ScopePromotionCommands]:
    policy = Policy(allowed)
    commands = ScopePromotionCommands()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.scope_promotion_service = commands
    return TestClient(app), policy, commands


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


@pytest.mark.integration
def test_authorized_manager_submits_a_scope_promotion(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/scope-promotions",
            headers=headers(),
            json={
                "current_scope_unit_id": str(TEAM_UNIT),
                "target_scope_unit_id": str(GROUP_UNIT),
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == ScopePromotionStatus.AWAITING_REVIEW.value
    assert policy.checks[0].relation == "can_manage"
    assert commands.submissions[0]["requested_by"] == AUTHOR


@pytest.mark.integration
def test_denied_submission_never_reaches_the_service(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=False)
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/scope-promotions",
            headers=headers(),
            json={
                "current_scope_unit_id": str(TEAM_UNIT),
                "target_scope_unit_id": str(GROUP_UNIT),
            },
        )

    assert response.status_code == 403
    assert commands.submissions == []


@pytest.mark.integration
def test_apply_widens_the_scope_end_to_end(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=True)
    commands.record = (
        opened()
        .review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        .approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
    )
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/scope-promotions/{REQUEST}/apply",
            headers=headers(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == ScopePromotionStatus.APPLIED.value
