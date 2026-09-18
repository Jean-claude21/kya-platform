"""Governed application registry HTTP contract."""

from collections.abc import Sequence
from uuid import UUID

from fastapi.testclient import TestClient

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.applications import RegisteredApplication
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.config import Settings
from kya_platform.main import create_app

PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")
ARTIFACT_ID = "01991c00-0000-7000-8000-000000000001"
WORKSPACE_ID = "01991c00-0000-7000-8000-000000000002"


def principal() -> AuthorizedPrincipal:
    return AuthorizedPrincipal(
        PRINCIPAL_ID,
        AuthenticatedIdentity("https://issuer.test", "subject", {}),
        "direction-cvsi",
    )


class Policy:
    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        allowed = request.relation in {"can_view", "can_submit"}
        return AuthorizationDecision(allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return (f"artifact:{ARTIFACT_ID}",)


class Applications:
    def __init__(self, *, internal_id: str = ARTIFACT_ID) -> None:
        self.internal_id = internal_id
        self.allowed_ids: tuple[str, ...] | None = None

    async def list_applications(
        self, *, allowed_ids: tuple[str, ...]
    ) -> tuple[RegisteredApplication, ...]:
        self.allowed_ids = allowed_ids
        return (
            RegisteredApplication(
                artifact_id="kya:app:kya-forms",
                internal_id=self.internal_id,
                name="KYA Forms",
                summary="Formulaires gouvernés.",
                version="0.1.0",
                lifecycle="published",
                owner_workspace_id=WORKSPACE_ID,
                launch_url="https://forms.kya.example/",
                launch_mode="same-tab",
                icon_url="https://forms.kya.example/icon.svg",
                health_url="https://forms.kya.example/health",
                required_sdk=">=0.1.0",
                visibility="restricted",
                default_scope="workspace",
                allowed_scopes=("workspace", "unit", "group"),
                declared_permissions=("view", "use", "create", "edit", "administer"),
                features=("forms.builder",),
            ),
        )


def _client(applications: Applications) -> TestClient:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    app.state.authorization = Policy()
    app.state.registry_mcp_backend = applications
    return TestClient(app, raise_server_exceptions=False)


def test_lists_only_authorized_launchable_applications_with_effective_permissions() -> None:
    applications = Applications()
    with _client(applications) as client:
        response = client.get("/api/v1/applications")

    assert response.status_code == 200
    body = response.json()
    assert body["active_unit"] == "direction-cvsi"
    assert body["items"][0]["artifact_id"] == "kya:app:kya-forms"
    assert body["items"][0]["enabled"] is True
    assert body["items"][0]["effective_permissions"] == ["view", "use", "create", "edit"]
    assert applications.allowed_ids == (ARTIFACT_ID,)


def test_get_application_does_not_disclose_an_unknown_application() -> None:
    with _client(Applications()) as client:
        response = client.get("/api/v1/applications/kya:app:unknown")

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"


def test_registry_rejects_a_backend_item_outside_the_authorized_set() -> None:
    with _client(Applications(internal_id="01991c00-0000-7000-8000-000000000099")) as client:
        response = client.get("/api/v1/applications")

    assert response.status_code == 500
