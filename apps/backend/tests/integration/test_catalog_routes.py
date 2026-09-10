"""HTTP catalog discovery shares the permission-first application service."""

from collections.abc import Sequence
from uuid import UUID

from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.catalog import CatalogBrowseQuery, CatalogDetail, CatalogSummary
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.config import Settings
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.installation_plan import (
    InstallationPlan,
    InstallationProfile,
    InstallationScope,
    build_installation_plan,
)
from kya_platform.main import create_app
from kya_platform.mcp.registry.contracts import (
    ConfirmInstallationInput,
    ConfirmUpdateInput,
    InstallationRecorded,
    ListUpdatesOutput,
    ManageInstallationInput,
    OperationAccepted,
    OperationStatus,
    RequestInstallInput,
    RequestUpdateInput,
)

PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")
RELEASE_ID = UUID("01991c00-0000-7000-8000-000000000099")
ARTIFACT_ID = UUID("01991c00-0000-7000-8000-000000000001")
INSTALLATION_ID = UUID("01991c00-0000-7000-8000-000000000010")
OPERATION_ID = UUID("01991c00-0000-7000-8000-000000000020")
WORKSPACE_ID = "01991c00-0000-7000-8000-000000000002"
CONTENT_DIGEST = "a" * 64
CONFIRMATION = {"confirmed": True}


def principal() -> AuthorizedPrincipal:
    return AuthorizedPrincipal(
        PRINCIPAL_ID,
        AuthenticatedIdentity("https://issuer.test", "subject", {}),
        "direction-cvsi",
    )


class Policy:
    """Grants can_view/can_edit/can_manage on the fixed workspace only."""

    def __init__(
        self,
        *,
        allowed_relations: tuple[str, ...] = ("can_view", "can_edit", "can_manage"),
    ) -> None:
        self.allowed_relations = allowed_relations
        self.checked: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checked.append(request)
        allowed = (
            request.object == f"workspace:{WORKSPACE_ID}"
            and request.relation in self.allowed_relations
        )
        return AuthorizationDecision(allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return (f"artifact:{ARTIFACT_ID}",)


class Catalog:
    """Fake registry backend covering discovery and distribution operations."""

    def __init__(self) -> None:
        self.received: CatalogBrowseQuery | None = None
        self.allowed_ids: tuple[str, ...] | None = None
        self.confirm_installation_calls: list[ConfirmInstallationInput] = []
        self.request_update_calls: list[RequestUpdateInput] = []
        self.confirm_update_calls: list[ConfirmUpdateInput] = []
        self.manage_installation_calls: list[ManageInstallationInput] = []
        self.raise_on_request_install: ToolError | None = None
        self.raise_on_confirm_installation: ToolError | None = None
        self.raise_on_request_update: ToolError | None = None
        self.raise_on_confirm_update: ToolError | None = None
        self.raise_on_manage_installation: ToolError | None = None

    async def browse(
        self, *, query: CatalogBrowseQuery, allowed_ids: tuple[str, ...]
    ) -> tuple[CatalogSummary, ...]:
        self.received = query
        self.allowed_ids = allowed_ids
        return (
            CatalogSummary(
                id=str(ARTIFACT_ID),
                public_id="kya:skill:kya-design-system",
                name="KYA Design System",
                artifact_type="skill",
                summary="Design system officiel du Groupe.",
                latest_version="1.0.0",
                lifecycle="published",
                owner_workspace_id=WORKSPACE_ID,
            ),
        )

    async def resolve_artifact_id(self, public_id: str) -> UUID | None:
        if public_id != "kya:skill:kya-design-system":
            return None
        return ARTIFACT_ID

    async def describe(self, *, public_id: str, version: str | None = None) -> CatalogDetail | None:
        if await self.resolve_artifact_id(public_id) is None:
            return None
        return CatalogDetail(
            id=str(ARTIFACT_ID),
            public_id=public_id,
            name="KYA Design System",
            artifact_type="skill",
            summary="Design system officiel du Groupe.",
            latest_version=version or "1.0.0",
            versions=("1.0.0", "0.9.0"),
            lifecycle="published",
            owner_workspace_id=WORKSPACE_ID,
            installable=True,
            risk="read",
            source_repository="https://github.com/kya-energy/kya-platform",
            content_digest=CONTENT_DIGEST,
        )

    async def resolve_release_id(self, public_id: str, version: str) -> UUID | None:
        if public_id != "kya:skill:kya-design-system":
            return None
        if version not in ("1.0.0", "0.9.0"):
            return None
        return RELEASE_ID

    async def resolve_installation_workspace(self, installation_id: UUID) -> str | None:
        if installation_id != INSTALLATION_ID:
            return None
        return WORKSPACE_ID

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None:
        if operation_id != OPERATION_ID:
            return None
        return WORKSPACE_ID

    async def request_install(self, request: RequestInstallInput) -> InstallationPlan:
        if self.raise_on_request_install is not None:
            raise self.raise_on_request_install
        return build_installation_plan(
            release_id=request.release_id,
            artifact_id=ARTIFACT_ID,
            artifact_type=ArtifactType.SKILL,
            artifact_slug="kya-design-system",
            version="1.0.0",
            profile=request.profile,
            scope=request.scope,
            target=request.target,
            package_locator="https://github.com/kya-energy/kya-platform/releases/download/x/x.zip",
            content_digest=CONTENT_DIGEST,
            compatibility_requirement=">=1.0.0",
            client_version=request.client_version,
            file_count=3,
            package_size=1024,
        )

    async def confirm_installation(self, request: ConfirmInstallationInput) -> InstallationRecorded:
        self.confirm_installation_calls.append(request)
        if self.raise_on_confirm_installation is not None:
            raise self.raise_on_confirm_installation
        return InstallationRecorded(installation_id=INSTALLATION_ID, operation_id=OPERATION_ID)

    async def list_updates(self, request: object) -> ListUpdatesOutput:
        return ListUpdatesOutput(items=())

    async def request_update(self, request: RequestUpdateInput) -> OperationAccepted:
        self.request_update_calls.append(request)
        if self.raise_on_request_update is not None:
            raise self.raise_on_request_update
        return OperationAccepted(operation_id=OPERATION_ID)

    async def confirm_update(self, request: ConfirmUpdateInput) -> OperationStatus:
        self.confirm_update_calls.append(request)
        if self.raise_on_confirm_update is not None:
            raise self.raise_on_confirm_update
        return OperationStatus(operation_id=OPERATION_ID, status="succeeded")

    async def manage_installation(self, request: ManageInstallationInput) -> OperationStatus:
        self.manage_installation_calls.append(request)
        if self.raise_on_manage_installation is not None:
            raise self.raise_on_manage_installation
        return OperationStatus(operation_id=OPERATION_ID, status="rolled-back")

    async def get_operation(self, request: object) -> OperationStatus:
        return OperationStatus(operation_id=OPERATION_ID, status="succeeded")


def _client(catalog: Catalog, policy: Policy) -> TestClient:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    app.state.authorization = policy
    app.state.registry_mcp_backend = catalog
    return TestClient(app)


def test_browse_returns_only_sanitized_authorized_capabilities() -> None:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    catalog = Catalog()
    app.state.authorization = Policy()
    app.state.registry_mcp_backend = catalog

    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/artifacts?query=design&artifact_type=skill&limit=10")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "artifact_id": "kya:skill:kya-design-system",
                "artifact_type": "skill",
                "name": "KYA Design System",
                "summary": "Design system officiel du Groupe.",
                "latest_version": "1.0.0",
                "lifecycle": "published",
                "owner_workspace_id": WORKSPACE_ID,
            }
        ],
        "active_unit": "direction-cvsi",
        "has_more": False,
    }
    assert catalog.allowed_ids == (str(ARTIFACT_ID),)
    assert catalog.received == CatalogBrowseQuery(
        query="design",
        artifact_types=("skill",),
        owner_workspace_id=None,
        limit=10,
    )


def test_browse_fails_closed_when_authorization_is_unavailable() -> None:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    app.state.authorization = None
    app.state.registry_mcp_backend = Catalog()

    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/artifacts")

    assert response.status_code == 503
    assert response.json()["code"] == "catalog_unavailable"


def test_detail_returns_version_provenance_and_installability() -> None:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    app.state.authorization = Policy()
    app.state.registry_mcp_backend = Catalog()

    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/artifacts/kya:skill:kya-design-system?version=1.0.0")

    assert response.status_code == 200
    assert response.json()["versions"] == ["1.0.0", "0.9.0"]
    assert response.json()["installable"] is True
    assert response.json()["risk"] == "read"
    assert response.json()["content_digest"] == CONTENT_DIGEST


def test_detail_does_not_distinguish_unknown_from_unauthorized() -> None:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    app.state.authorization = Policy()
    app.state.registry_mcp_backend = Catalog()

    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/artifacts/kya:skill:unknown")

    assert response.status_code == 404
    assert response.json()["code"] == "catalog_artifact_not_found"


def _install_plan_payload() -> dict[str, object]:
    return {
        "version": "1.0.0",
        "target": f"workspace:{WORKSPACE_ID}",
        "profile": InstallationProfile.CODEX.value,
        "scope": InstallationScope.PERSONAL.value,
        "client_version": "1.2.0",
        "confirmation": CONFIRMATION,
    }


def test_installation_plan_requires_can_edit_and_returns_deterministic_plan() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post(
            "/api/v1/catalog/artifacts/kya:skill:kya-design-system/installation-plan",
            json=_install_plan_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["release_id"] == str(RELEASE_ID)
    assert body["server_writes_local_files"] is False
    assert body["requires_client_confirmation"] is True
    assert len(body["steps"]) == 7


def test_installation_plan_denied_without_can_edit() -> None:
    catalog = Catalog()
    policy = Policy(allowed_relations=("can_view",))
    with _client(catalog, policy) as client:
        response = client.post(
            "/api/v1/catalog/artifacts/kya:skill:kya-design-system/installation-plan",
            json=_install_plan_payload(),
        )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_installation_plan_rejects_non_workspace_target() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        payload = _install_plan_payload()
        payload["target"] = "personal:someone"
        response = client.post(
            "/api/v1/catalog/artifacts/kya:skill:kya-design-system/installation-plan",
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_installation_target"


def test_installation_plan_does_not_resolve_release_for_unauthorized_artifact() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post(
            "/api/v1/catalog/artifacts/kya:skill:unknown/installation-plan",
            json=_install_plan_payload(),
        )

    assert response.status_code == 404
    assert response.json()["code"] == "catalog_artifact_not_found"


def test_installation_plan_maps_tool_error_to_sanitized_conflict() -> None:
    catalog = Catalog()
    catalog.raise_on_request_install = ToolError("idempotency_key_conflict")
    with _client(catalog, Policy()) as client:
        response = client.post(
            "/api/v1/catalog/artifacts/kya:skill:kya-design-system/installation-plan",
            json=_install_plan_payload(),
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "idempotency_key_conflict"
    assert "traceback" not in body


def _receipt_payload() -> dict[str, object]:
    return {
        "plan_id": str(UUID("01991c00-0000-7000-8000-000000000030")),
        "release_id": str(RELEASE_ID),
        "target": f"workspace:{WORKSPACE_ID}",
        "profile": InstallationProfile.CODEX.value,
        "scope": InstallationScope.PERSONAL.value,
        "client_version": "1.2.0",
        "installed_digest": CONTENT_DIGEST,
        "idempotency_key": "installation-receipt-0001",
        "confirmation": CONFIRMATION,
    }


def test_installation_receipt_forces_actor_id_from_principal() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post("/api/v1/catalog/installation-receipts", json=_receipt_payload())

    assert response.status_code == 200
    assert response.json() == {
        "installation_id": str(INSTALLATION_ID),
        "operation_id": str(OPERATION_ID),
        "status": "active",
    }
    assert len(catalog.confirm_installation_calls) == 1
    assert catalog.confirm_installation_calls[0].actor_id == PRINCIPAL_ID


def test_installation_receipt_denied_without_can_edit() -> None:
    catalog = Catalog()
    policy = Policy(allowed_relations=("can_view",))
    with _client(catalog, policy) as client:
        response = client.post("/api/v1/catalog/installation-receipts", json=_receipt_payload())

    assert response.status_code == 403


def test_installation_receipt_rejects_missing_confirmation() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        payload = _receipt_payload()
        payload["confirmation"] = {"confirmed": False}
        response = client.post("/api/v1/catalog/installation-receipts", json=payload)

    assert response.status_code == 422


def test_list_updates_requires_can_view_and_resolves_installation_workspace() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.get(f"/api/v1/catalog/installations/{INSTALLATION_ID}/updates")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_updates_unknown_installation_returns_generic_404() -> None:
    catalog = Catalog()
    unknown_id = UUID("01991c00-0000-7000-8000-000000000099")
    with _client(catalog, Policy()) as client:
        response = client.get(f"/api/v1/catalog/installations/{unknown_id}/updates")

    assert response.status_code == 404
    assert response.json()["code"] == "installation_not_found"


def test_request_update_requires_can_edit() -> None:
    catalog = Catalog()
    policy = Policy(allowed_relations=("can_view",))
    with _client(catalog, policy) as client:
        response = client.post(
            f"/api/v1/catalog/installations/{INSTALLATION_ID}/updates",
            json={
                "release_id": str(RELEASE_ID),
                "idempotency_key": "update-request-00001",
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 403


def test_request_update_accepted_with_can_edit() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post(
            f"/api/v1/catalog/installations/{INSTALLATION_ID}/updates",
            json={
                "release_id": str(RELEASE_ID),
                "idempotency_key": "update-request-00001",
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 200
    assert response.json()["operation_id"] == str(OPERATION_ID)
    assert catalog.request_update_calls[0].actor_id == PRINCIPAL_ID


def test_confirm_update_receipt_requires_can_edit() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post(
            f"/api/v1/catalog/operations/{OPERATION_ID}/update-receipt",
            json={
                "installed_digest": CONTENT_DIGEST,
                "expected_revision": 2,
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 200
    assert catalog.confirm_update_calls[0].actor_id == PRINCIPAL_ID


def test_confirm_update_unknown_operation_returns_generic_404() -> None:
    catalog = Catalog()
    unknown_id = UUID("01991c00-0000-7000-8000-000000000098")
    with _client(catalog, Policy()) as client:
        response = client.post(
            f"/api/v1/catalog/operations/{unknown_id}/update-receipt",
            json={
                "installed_digest": CONTENT_DIGEST,
                "expected_revision": 2,
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 404
    assert response.json()["code"] == "operation_not_found"


def test_manage_installation_rollback_requires_can_manage() -> None:
    catalog = Catalog()
    policy = Policy(allowed_relations=("can_view", "can_edit"))
    with _client(catalog, policy) as client:
        response = client.post(
            f"/api/v1/catalog/installations/{INSTALLATION_ID}/actions",
            json={
                "action": "rollback",
                "expected_revision": 3,
                "idempotency_key": "rollback-000000001",
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 403


def test_manage_installation_rollback_succeeds_with_can_manage() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.post(
            f"/api/v1/catalog/installations/{INSTALLATION_ID}/actions",
            json={
                "action": "rollback",
                "expected_revision": 3,
                "idempotency_key": "rollback-000000001",
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rolled-back"
    assert catalog.manage_installation_calls[0].actor_id == PRINCIPAL_ID


def test_manage_installation_maps_revision_conflict() -> None:
    catalog = Catalog()
    catalog.raise_on_manage_installation = ToolError("installation_revision_conflict")
    with _client(catalog, Policy()) as client:
        response = client.post(
            f"/api/v1/catalog/installations/{INSTALLATION_ID}/actions",
            json={
                "action": "rollback",
                "expected_revision": 1,
                "idempotency_key": "rollback-000000002",
                "confirmation": CONFIRMATION,
            },
        )

    assert response.status_code == 409
    assert response.json()["code"] == "installation_revision_conflict"


def test_get_operation_requires_can_view_and_returns_generic_404_for_unknown() -> None:
    catalog = Catalog()
    unknown_id = UUID("01991c00-0000-7000-8000-000000000097")
    with _client(catalog, Policy()) as client:
        response = client.get(f"/api/v1/catalog/operations/{unknown_id}")

    assert response.status_code == 404
    assert response.json()["code"] == "operation_not_found"


def test_get_operation_succeeds_with_can_view() -> None:
    catalog = Catalog()
    with _client(catalog, Policy()) as client:
        response = client.get(f"/api/v1/catalog/operations/{OPERATION_ID}")

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
