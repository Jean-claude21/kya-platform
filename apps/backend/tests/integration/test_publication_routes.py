"""Publication routes enforce artifact permissions before workflow execution."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.publication.evidence import AttestationKind, AttestationRecord
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.catalog import ArtifactVersion, PublicationRequest

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
ARTIFACT = UUID("019914b2-1a40-7000-8000-0000000000a1")
REQUEST = UUID("019914b2-1a40-7000-8000-0000000000b1")
VERSION = UUID("019914b2-1a40-7000-8000-0000000000b2")
EVIDENCE = UUID("019914b2-1a40-7000-8000-0000000000b3")


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


class Attestations:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **values: object) -> AttestationRecord:
        self.calls.append(values)
        return AttestationRecord(
            EVIDENCE,
            VERSION,
            AttestationKind.PROVENANCE,
            AUTHOR,
            "b" * 64,
            "passed",
            datetime(2026, 9, 7, tzinfo=UTC),
            None,
            "https://evidence.kya.energy/provenance/1",
        )


def configure(app: FastAPI, *, allowed: bool) -> tuple[TestClient, Policy, PublicationCommands]:
    policy = Policy(allowed)
    commands = PublicationCommands()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.publication_service = commands
    app.state.attestation_repository = Attestations()
    return TestClient(app), policy, commands


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


def candidate_body() -> dict[str, object]:
    return {
        "version": "1.0.0",
        "commit_sha": "a" * 40,
        "content_digest": "b" * 64,
        "manifest_digest": "c" * 64,
        "evidence_ids": [str(EVIDENCE)],
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
    assert commands.submissions[0]["evidence_ids"] == (EVIDENCE,)


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


@pytest.mark.integration
def test_authorized_reviewer_records_digest_bound_evidence(app: FastAPI) -> None:
    client, policy, _commands = configure(app, allowed=True)
    with client:
        response = client.post(
            f"/api/v1/artifacts/{ARTIFACT}/versions/{VERSION}/attestations",
            headers=headers(),
            json={
                "kind": "provenance",
                "result": "passed",
                "evidence_uri": "https://evidence.kya.energy/provenance/1",
            },
        )

    assert response.status_code == 201
    assert response.json()["subject_digest"] == "b" * 64
    assert policy.checks[0].relation == "can_review"
