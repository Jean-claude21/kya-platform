"""Artifact API tests prove workspace authorization precedes data access."""

from collections.abc import Sequence
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.artifact_registry import ArtifactRecord
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.contracts.artifact_package import ArtifactPackage

WORKSPACE = UUID("01991b00-0000-7000-8000-000000000001")
OWNER = UUID("01991b00-0000-7000-8000-000000000002")
ACTOR = UUID("01991b00-0000-7000-8000-000000000004")


def package_payload() -> dict[str, object]:
    return {
        "schemaVersion": "1",
        "artifact": {
            "schemaVersion": "1",
            "id": "kya:skill:document-standard",
            "type": "skill",
            "name": "Standard documentaire KYA",
            "version": "1.0.0",
            "owners": {
                "business": "communication",
                "technical": "cvsi-platform",
                "workspace": "communication",
            },
            "source": {
                "repository": "https://github.com/kya-energy/document-standard",
                "commit": "a" * 40,
            },
            "integrity": {"algorithm": "sha256", "digest": "b" * 64},
            "compatibility": {"codex": ">=2026-09"},
        },
        "files": [
            {
                "path": "artifact.manifest.json",
                "mediaType": "application/json",
                "size": 600,
                "sha256": "c" * 64,
                "kind": "manifest",
            },
            {
                "path": "SKILL.md",
                "mediaType": "text/markdown",
                "size": 900,
                "sha256": "d" * 64,
                "kind": "instruction",
            },
        ],
    }


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "author", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ACTOR


class Policy:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


class RegistryService:
    def __init__(self) -> None:
        self.created = False

    async def create_draft(self, **values: object) -> ArtifactRecord:
        self.created = True
        package = values["package"]
        assert isinstance(package, ArtifactPackage)
        return ArtifactRecord(
            UUID("01991b00-0000-7000-8000-000000000010"),
            UUID("01991b00-0000-7000-8000-000000000011"),
            WORKSPACE,
            "document-standard",
            "draft",
            "draft",
            package,
        )


def configure(app: FastAPI, allowed: bool) -> tuple[TestClient, Policy, RegistryService]:
    policy = Policy(allowed)
    registry = RegistryService()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.artifact_registry = registry
    return TestClient(app), policy, registry


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


def request_body() -> dict[str, object]:
    return {
        "slug": "document-standard",
        "business_owner_id": str(OWNER),
        "technical_owner_id": str(OWNER),
        "package": package_payload(),
    }


@pytest.mark.integration
def test_authorized_contributor_creates_a_validated_draft(app: FastAPI) -> None:
    client, policy, registry = configure(app, True)
    with client:
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE}/artifacts",
            headers=headers(),
            json=request_body(),
        )

    assert response.status_code == 201
    assert response.json()["package"]["artifact"]["id"] == "kya:skill:document-standard"
    assert policy.checks[0].relation == "can_edit"
    assert registry.created is True


@pytest.mark.integration
def test_denied_contributor_never_reaches_registry(app: FastAPI) -> None:
    client, _policy, registry = configure(app, False)
    with client:
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE}/artifacts",
            headers=headers(),
            json=request_body(),
        )

    assert response.status_code == 403
    assert registry.created is False
