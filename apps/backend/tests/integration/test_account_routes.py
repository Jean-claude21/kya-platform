"""Authenticated account bootstrap binds Neon identities to KYA principals."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity

EXISTING_ID = UUID("019914b2-1a40-7000-8000-000000000041")


class AccountVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        assert token == "valid-token"
        return AuthenticatedIdentity(
            issuer="https://auth.example.neon.tech",
            subject="neon-user-456",
            claims={"email": "alice@kya-energy.com"},
        )


class AccountMapping:
    def __init__(self, principal_id: UUID | None) -> None:
        self.principal_id = principal_id
        self.provisioned: UUID | None = None

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        assert identity.subject == "neon-user-456"
        return self.principal_id

    async def provision_identity(self, identity: AuthenticatedIdentity, principal_id: UUID) -> UUID:
        assert identity.subject == "neon-user-456"
        self.provisioned = principal_id
        return principal_id


def authenticate(app: FastAPI, mapping: AccountMapping | None) -> None:
    app.state.token_verifier = AccountVerifier()
    app.state.identity_mapping = mapping


@pytest.mark.integration
def test_account_returns_existing_principal_in_explicit_context(app: FastAPI) -> None:
    authenticate(app, AccountMapping(EXISTING_ID))

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer valid-token", "X-KYA-Unit-ID": "direction-cvsi"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "principal_id": str(EXISTING_ID),
        "email": "alice@kya-energy.com",
        "active_unit_id": "direction-cvsi",
        "mcp_ready": True,
    }


@pytest.mark.integration
def test_account_provisions_an_unmapped_identity_without_granting_roles(app: FastAPI) -> None:
    mapping = AccountMapping(None)
    authenticate(app, mapping)

    with TestClient(app) as client:
        response = client.get("/api/v1/account/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json()["principal_id"] == str(mapping.provisioned)
    assert response.json()["active_unit_id"] == "group"


@pytest.mark.integration
def test_account_fails_closed_without_identity_storage(app: FastAPI) -> None:
    authenticate(app, None)

    with TestClient(app) as client:
        response = client.get("/api/v1/account/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 503
    assert response.json()["code"] == "identity_provisioning_unavailable"
