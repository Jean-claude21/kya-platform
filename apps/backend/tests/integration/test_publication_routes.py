"""Publication routes enforce artifact permissions before workflow execution."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.catalog import ArtifactVersion, PublicationRequest

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
ARTIFACT = UUID("019914b2-1a40-7000-8000-0000000000a1")
REQUEST = UUID("019914b2-1a40-7000-8000-0000000000b1")


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


class PublicationCommands:
    def __init__(self) -> None:
        self.submissions: list[dict[str, object]] = []
        self.raise_on_review = False

    async def submit(self, **values: object) -> PublicationRequest:
        self.submissions.append(values)
        candidate = values["candidate"]
        assert isinstance(candidate, ArtifactVersion)
        at = values["at"]
        assert isinstance(at, datetime)
        return PublicationRequest.open(
            id=REQUEST,
            candidate=candidate,
            requested_by=AUTHOR,
            requested_at=at,
            separation_of_duties=True,
        )

    async def review(self, *args: object, **kwargs: object) -> PublicationRequest:
        if self.raise_on_review:
            raise PermissionError("internal actor details")
        raise AssertionError("not expected")


def configure(app: FastAPI, *, allowed: bool) -> tuple[TestClient, Policy, PublicationCommands]:
    policy = Policy(allowed)
    commands = PublicationCommands()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.publication_service = commands
    return TestClient(app), policy, commands


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


def candidate_body() -> dict[str, str]:
    return {
        "version": "1.0.0",
        "commit_sha": "a" * 40,
        "content_digest": "b" * 64,
        "manifest_digest": "c" * 64,
    }


@pytest.mark.integration
def test_authorized_author_submits_a_frozen_candidate(app: FastAPI) -> None:
    client, policy, commands = configure(app, allowed=True)
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/publication-requests",
            headers=headers(),
            json=candidate_body(),
        )

    assert response.status_code == 202
    assert response.json()["content_digest"] == "b" * 64
    assert policy.checks[0].relation == "can_submit"
    assert commands.submissions[0]["separation_of_duties"] is True


@pytest.mark.integration
def test_denied_submission_never_reaches_publication_service(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=False)
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/publication-requests",
            headers=headers(),
            json=candidate_body(),
        )

    assert response.status_code == 403
    assert commands.submissions == []


@pytest.mark.integration
def test_separation_conflict_returns_safe_public_error(app: FastAPI) -> None:
    client, _policy, commands = configure(app, allowed=True)
    commands.raise_on_review = True
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/publication-requests/{REQUEST}/reviews",
            headers=headers(),
            json={"decision": "accepted"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "publication_duty_conflict"
    assert "internal actor details" not in response.text
