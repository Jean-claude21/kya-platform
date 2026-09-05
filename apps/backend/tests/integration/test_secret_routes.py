"""Secret administration exposes governance metadata and never values."""

from datetime import UTC, datetime
from uuid import UUID, uuid7

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.secrets import SecretKind, SecretReference, SecretStatus

ALICE = UUID("019914b2-1a40-7000-8000-000000000051")


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class Policy:
    def __init__(self, listed: tuple[str, ...], *, allowed: bool = True) -> None:
        self.listed = listed
        self.allowed = allowed

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(self.allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return self.listed


class References:
    def __init__(self, visible: SecretReference, hidden: SecretReference) -> None:
        self.records = {visible.id: visible, hidden.id: hidden}
        self.loaded_ids: tuple[UUID, ...] = ()

    async def get(self, reference_id: UUID) -> SecretReference | None:
        return self.records.get(reference_id)

    async def list_for_scope(self, owner_scope: str) -> tuple[SecretReference, ...]:
        return tuple(item for item in self.records.values() if item.owner_scope == owner_scope)

    async def list_by_ids(self, reference_ids: tuple[UUID, ...]) -> tuple[SecretReference, ...]:
        self.loaded_ids = reference_ids
        return tuple(self.records[item] for item in reference_ids if item in self.records)

    async def register(self, reference: SecretReference) -> None:
        self.records[reference.id] = reference

    async def revoke(self, reference_id: UUID) -> None:
        current = self.records[reference_id]
        self.records[reference_id] = current.model_copy(update={"status": SecretStatus.REVOKED})


def secret(name: str) -> SecretReference:
    return SecretReference(
        id=uuid7(),
        kind=SecretKind.SERVICE,
        provider="infisical",
        locator=f"kya/preview/{name}",
        key_name=name,
        owner_scope="workspace:platform",
        purpose="Déployer une preview",
        environment="preview",
        status=SecretStatus.ACTIVE,
        created_at=datetime(2026, 9, 4, tzinfo=UTC),
    )


def configured(app: FastAPI, policy: Policy, references: References) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.secret_references = references
    return TestClient(app)


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


@pytest.mark.integration
def test_list_filters_ids_before_loading_and_never_returns_values(app: FastAPI) -> None:
    visible, hidden = secret("DOKPLOY_TOKEN"), secret("HIDDEN_TOKEN")
    references = References(visible, hidden)
    policy = Policy((f"secret_reference:{visible.id}",))

    with configured(app, policy, references) as client:
        response = client.get("/api/v1/secrets", headers=headers())

    assert response.status_code == 200
    assert references.loaded_ids == (visible.id,)
    assert [item["id"] for item in response.json()["items"]] == [str(visible.id)]
    assert "HIDDEN_TOKEN" not in response.text
    assert "value" not in response.text


@pytest.mark.integration
def test_registration_rejects_secret_material(app: FastAPI) -> None:
    visible, hidden = secret("DOKPLOY_TOKEN"), secret("HIDDEN_TOKEN")
    references = References(visible, hidden)

    with configured(app, Policy((), allowed=True), references) as client:
        response = client.put(
            f"/api/v1/secrets/{uuid7()}",
            headers=headers(),
            json={
                "kind": "service",
                "provider": "infisical",
                "locator": "kya/preview/deploy",
                "key_name": "DOKPLOY_TOKEN",
                "owner_scope": "workspace:platform",
                "purpose": "Déployer une preview",
                "environment": "preview",
                "value": "must-not-enter",
            },
        )

    assert response.status_code == 422
    assert "must-not-enter" not in response.text


@pytest.mark.integration
def test_revocation_requires_metadata_management_permission(app: FastAPI) -> None:
    visible, hidden = secret("DOKPLOY_TOKEN"), secret("HIDDEN_TOKEN")
    references = References(visible, hidden)

    with configured(app, Policy((), allowed=False), references) as client:
        response = client.delete(f"/api/v1/secrets/{visible.id}", headers=headers())

    assert response.status_code == 403
    assert references.records[visible.id].status is SecretStatus.ACTIVE
