"""End-to-end dependency tests for the API security chain."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.auth import AuthenticatedIdentity, InvalidTokenError
from kya_platform.authorization import (
    AuthorizationDecision,
    CheckRequest,
    ListObjectsRequest,
)
from kya_platform.config import Settings
from kya_platform.main import create_app

PRINCIPAL_ID = UUID("019914b2-1a40-7000-8000-000000000031")


class AcceptingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        assert token == "valid-token"
        return AuthenticatedIdentity(
            issuer="https://auth.example.neon.tech",
            subject="neon-user-123",
            claims={},
        )


class RejectingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        raise InvalidTokenError("signature details must not escape")


class StaticIdentityMapping:
    def __init__(self, principal_id: UUID | None = PRINCIPAL_ID) -> None:
        self.principal_id = principal_id

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        assert identity.subject == "neon-user-123"
        return self.principal_id


class RecordingAuthorization:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.requests: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.requests.append(request)
        return AuthorizationDecision(allowed=self.allowed, model_id="01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


def install_guarded_route(app: FastAPI) -> None:
    guard = require_permission(
        relation="can_view",
        object_type="workspace",
        object_parameter="workspace_id",
    )

    async def guarded(
        workspace_id: str,
        principal: Annotated[AuthorizedPrincipal, Depends(guard)],
    ) -> dict[str, str]:
        return {"workspace_id": workspace_id, "principal_id": str(principal.principal_id)}

    app.add_api_route("/api/v1/test-workspaces/{workspace_id}", guarded)


def configure_fakes(app: FastAPI, *, allowed: bool = True) -> RecordingAuthorization:
    authorization = RecordingAuthorization(allowed)
    app.state.token_verifier = AcceptingVerifier()
    app.state.identity_mapping = StaticIdentityMapping()
    app.state.authorization = authorization
    return authorization


@pytest.mark.security
def test_bearer_token_is_required(app: FastAPI) -> None:
    install_guarded_route(app)
    configure_fakes(app)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={"X-KYA-Unit-ID": "direction-cvsi"},
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["code"] == "authentication_required"


@pytest.mark.security
def test_invalid_token_is_rejected_without_verifier_details(app: FastAPI) -> None:
    install_guarded_route(app)
    configure_fakes(app)
    app.state.token_verifier = RejectingVerifier()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={
                "Authorization": "Bearer invalid-token",
                "X-KYA-Unit-ID": "direction-cvsi",
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_authentication_token"
    assert "signature details" not in response.text


@pytest.mark.security
def test_unconfigured_authentication_fails_closed(app: FastAPI) -> None:
    install_guarded_route(app)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={
                "Authorization": "Bearer unavailable",
                "X-KYA-Unit-ID": "direction-cvsi",
            },
        )

    assert response.status_code == 503
    assert response.json()["code"] == "authentication_unavailable"


@pytest.mark.security
def test_active_unit_is_required(app: FastAPI) -> None:
    install_guarded_route(app)
    configure_fakes(app)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "active_unit_required"


@pytest.mark.security
def test_guard_uses_internal_principal_and_contextual_unit(app: FastAPI) -> None:
    install_guarded_route(app)
    authorization = configure_fakes(app)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={
                "Authorization": "Bearer valid-token",
                "X-KYA-Unit-ID": "direction-cvsi",
            },
        )

    assert response.status_code == 200
    assert response.json()["principal_id"] == str(PRINCIPAL_ID)
    check = authorization.requests[0]
    assert check.user == f"user:{PRINCIPAL_ID}"
    assert check.object == "workspace:platform"
    assert check.contextual_tuples[0].object == "org_unit:direction-cvsi"


@pytest.mark.security
def test_guard_fails_closed_on_negative_decision(app: FastAPI) -> None:
    install_guarded_route(app)
    configure_fakes(app, allowed=False)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={
                "Authorization": "Bearer valid-token",
                "X-KYA-Unit-ID": "direction-cvsi",
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


@pytest.mark.security
def test_unlinked_neon_identity_is_denied(app: FastAPI) -> None:
    install_guarded_route(app)
    configure_fakes(app)
    app.state.identity_mapping = StaticIdentityMapping(None)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-workspaces/platform",
            headers={
                "Authorization": "Bearer valid-token",
                "X-KYA-Unit-ID": "direction-cvsi",
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "identity_not_linked"


@pytest.mark.unit
def test_partial_neon_auth_configuration_is_rejected() -> None:
    settings = Settings(environment="test", neon_auth_issuer="https://issuer.example")

    with pytest.raises(RuntimeError, match="configured together"):
        create_app(settings)
