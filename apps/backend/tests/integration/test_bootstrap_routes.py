"""The signed-in configured owner can initialize the platform without an operator."""

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.bootstrap import BootstrapClaim, BootstrapService, owner_fingerprint

OWNER_ID = UUID("01991fb0-6c00-7000-8000-000000000010")
CODE_HASH = "3538b4902a9fad43d80819555b9849c471a422489a4f4d7eb532217195e9293d"


class Verifier:
    async def verify(self, _: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity(
            issuer="https://auth.example.neon.tech",
            subject="owner-subject",
            claims={"email": "owner@kya-energy.com"},
        )


class Mapping:
    async def resolve_principal_id(self, _: AuthenticatedIdentity) -> UUID:
        return OWNER_ID

    async def provision_identity(self, _: AuthenticatedIdentity, principal_id: UUID) -> UUID:
        return principal_id


class Claims:
    claim: BootstrapClaim | None = None

    async def get(self) -> BootstrapClaim | None:
        return self.claim

    async def reserve(self, claim: BootstrapClaim) -> BootstrapClaim:
        self.claim = self.claim or claim
        return self.claim

    async def complete(self, principal_id: UUID) -> BootstrapClaim:
        self.claim = BootstrapClaim(
            principal_id, owner_fingerprint("owner@kya-energy.com"), "complete"
        )
        return self.claim


class Grant:
    granted = False

    async def grant_platform_owner(self, principal_id: UUID) -> None:
        assert principal_id == OWNER_ID
        self.granted = True


def configure(app: FastAPI) -> Grant:
    grant = Grant()
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.bootstrap_service = BootstrapService(
        repository=Claims(),
        grant=grant,
        owner_email="owner@kya-energy.com",
        claim_code_hash=SecretStr(CODE_HASH),
    )
    return grant


def test_owner_sees_pending_state_and_claims_platform(app: FastAPI) -> None:
    grant = configure(app)
    headers = {"Authorization": "Bearer valid-token"}

    with TestClient(app) as client:
        status = client.get("/api/v1/bootstrap/status", headers=headers)
        claimed = client.post(
            "/api/v1/bootstrap/claim",
            headers=headers,
            json={"claim_code": "one-time-code"},
        )

    assert status.json() == {"state": "pending", "eligible": True}
    assert claimed.status_code == 200
    assert claimed.json() == {
        "state": "complete",
        "principal_id": str(OWNER_ID),
        "role": "platform_owner",
    }
    assert grant.granted


def test_claim_code_is_never_echoed_in_rejection(app: FastAPI) -> None:
    configure(app)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/bootstrap/claim",
            headers={"Authorization": "Bearer valid-token"},
            json={"claim_code": "must-not-leak"},
        )

    assert response.status_code == 403
    assert "must-not-leak" not in response.text


def test_status_fails_closed_when_bootstrap_is_not_configured(app: FastAPI) -> None:
    app.state.token_verifier = Verifier()
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/bootstrap/status",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 503
    assert response.json()["code"] == "bootstrap_unavailable"
