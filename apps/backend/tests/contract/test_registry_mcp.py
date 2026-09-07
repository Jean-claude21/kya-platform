from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from starlette.testclient import TestClient

from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.authorization.service import AuthorizationService
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.installation_plan import InstallationPlan, build_installation_plan
from kya_platform.mcp.registry import (
    ArtifactDetail,
    ArtifactSummary,
    Confirmation,
    InstallationRecorded,
    ListUpdatesOutput,
    RequestInstallInput,
    SearchCatalogInput,
    SearchCatalogOutput,
    ToolAccessContext,
    ToolAuthorizer,
)
from kya_platform.mcp.registry.contracts import REGISTRY_TOOLS
from kya_platform.mcp.registry.server import RegistryGuard, create_registry_server


@dataclass
class RecordingPolicy:
    allowed: bool
    checks: list[CheckRequest]
    lists: list[ListObjectsRequest] = field(default_factory=list)

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(allowed=self.allowed, model_id="test-model")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        self.lists.append(request)
        if not self.allowed:
            return ()
        return ("artifact:11111111-1111-4111-8111-111111111111",)


def tool(name: str) -> Any:
    return next(item for item in REGISTRY_TOOLS if item.name == name)


def test_input_schemas_reject_undeclared_fields() -> None:
    with pytest.raises(ValidationError):
        SearchCatalogInput.model_validate({"query": "solaire", "secret": "leak"})


@pytest.mark.parametrize(
    "payload",
    [
        {
            "release_id": str(uuid4()),
            "target": "workspace:dss",
            "confirmation": {"confirmed": True},
        },
        {
            "release_id": str(uuid4()),
            "target": "workspace:dss",
            "idempotency_key": "request-00000001",
        },
        {
            "release_id": str(uuid4()),
            "target": "workspace:dss",
            "idempotency_key": "short",
            "confirmation": {"confirmed": True},
        },
    ],
)
def test_install_requires_confirmation_and_strong_idempotency(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RequestInstallInput.model_validate(payload)


def test_install_contract_accepts_explicit_confirmation() -> None:
    request = RequestInstallInput(
        release_id=uuid4(),
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        idempotency_key="install-request-0001",
        confirmation=Confirmation(confirmed=True),
    )
    assert request.confirmation.confirmed is True
    assert request.profile.value == "codex"


@pytest.mark.asyncio
async def test_oauth_scope_is_required_before_policy_check() -> None:
    policy = RecordingPolicy(allowed=True, checks=[])
    authorizer = ToolAuthorizer(AuthorizationService(policy))

    allowed = await authorizer.is_allowed(
        tool("search_catalog"),
        ToolAccessContext("user:alice", frozenset(), "global", {}),
    )

    assert allowed is False
    assert policy.checks == []


@pytest.mark.asyncio
async def test_registry_guard_rejects_missing_token_scope_and_active_unit() -> None:
    authorization = AuthorizationService(RecordingPolicy(allowed=True, checks=[]))
    with pytest.raises(ToolError, match="authentication_required"):
        await RegistryGuard(authorization, lambda: None).allowed_artifact_ids("search_catalog")

    missing_scope = AccessToken(
        token="token", client_id="client", subject="alice", scopes=[], claims={"active_unit": "dss"}
    )
    with pytest.raises(ToolError, match="scope_required"):
        await RegistryGuard(authorization, lambda: missing_scope).allowed_artifact_ids(
            "search_catalog"
        )

    missing_unit = AccessToken(
        token="token", client_id="client", subject="alice", scopes=["catalog:read"], claims={}
    )
    with pytest.raises(ToolError, match="active_unit_required"):
        await RegistryGuard(authorization, lambda: missing_unit).allowed_artifact_ids(
            "search_catalog"
        )


@pytest.mark.asyncio
async def test_kya_permission_remains_required_when_scope_is_present() -> None:
    policy = RecordingPolicy(allowed=False, checks=[])
    authorizer = ToolAuthorizer(AuthorizationService(policy))

    allowed = await authorizer.is_allowed(
        tool("request_install"),
        ToolAccessContext(
            "user:bob", frozenset({"catalog:install"}), "dss", {"active_unit": "dss"}
        ),
    )

    assert allowed is False
    assert policy.checks[0].object == "workspace:dss"
    assert policy.checks[0].relation == "can_edit"


@pytest.mark.asyncio
async def test_tool_list_is_reduced_for_the_caller() -> None:
    policy = RecordingPolicy(allowed=True, checks=[])
    authorizer = ToolAuthorizer(AuthorizationService(policy))
    visible = await authorizer.visible_tools(
        ToolAccessContext("user:alice", frozenset({"catalog:read"}), "global", {})
    )

    assert {item.name for item in visible} == {
        "search_catalog",
        "get_artifact",
        "list_updates",
        "get_operation",
    }


def test_skills_are_catalog_artifacts_not_executable_tools() -> None:
    assert all("skill" not in item.name for item in REGISTRY_TOOLS)


class NoopTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        return None


class SearchBackend:
    async def search_catalog(
        self, request: SearchCatalogInput, *, allowed_ids: tuple[str, ...]
    ) -> SearchCatalogOutput:
        if not allowed_ids:
            return SearchCatalogOutput(items=())
        assert allowed_ids == ("11111111-1111-4111-8111-111111111111",)
        return SearchCatalogOutput(
            items=(
                ArtifactSummary(
                    artifact_id="kya:skill:business-method",
                    artifact_type="skill",
                    name="Méthode métier KYA",
                    latest_version="0.1.0",
                ),
            )
        )

    async def resolve_artifact_id(self, public_id: str) -> UUID | None:
        return UUID("11111111-1111-4111-8111-111111111111")

    async def resolve_installation_workspace(self, installation_id: UUID) -> str | None:
        return "dss"

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None:
        return "dss"

    async def get_artifact(self, request: Any) -> ArtifactDetail:
        raise AssertionError("not called")

    async def list_updates(self, request: Any) -> ListUpdatesOutput:
        return ListUpdatesOutput(items=())

    async def request_install(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def confirm_installation(self, request: Any) -> InstallationRecorded:
        return InstallationRecorded(
            installation_id=UUID("01991e00-0000-7000-8000-000000000001"),
            operation_id=UUID("01991e00-0000-7000-8000-000000000002"),
        )

    async def request_update(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def confirm_update(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def manage_installation(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def get_operation(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def publish_candidate(self, request: Any) -> Any:
        raise AssertionError("not called")


def access_token() -> AccessToken:
    return AccessToken(
        token="opaque-test-token",
        client_id="codex-test",
        subject="alice",
        scopes=["catalog:read"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )


@pytest.mark.asyncio
async def test_registry_server_executes_authorized_search_in_memory() -> None:
    policy = RecordingPolicy(allowed=True, checks=[])
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(policy),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=access_token,
    )

    async with Client(server) as client:
        listed = await client.list_tools()
        result = await client.call_tool("search_catalog", {"query": "méthode"})

    assert "search_catalog" in {item.name for item in listed.tools}
    assert result.is_error is False
    assert result.structured_content["items"][0]["artifact_id"] == ("kya:skill:business-method")
    assert policy.lists[0].user == "user:alice"


@pytest.mark.asyncio
async def test_registry_server_authorizes_installation_reads_through_workspace() -> None:
    policy = RecordingPolicy(allowed=True, checks=[])
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(policy),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=access_token,
    )

    async with Client(server) as client:
        result = await client.call_tool("list_updates", {"installation_id": str(uuid4())})

    assert result.is_error is False
    assert policy.checks[0].object == "workspace:dss"
    assert policy.checks[0].relation == "can_view"


@pytest.mark.asyncio
async def test_registry_server_returns_stable_authorization_error() -> None:
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=False, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=access_token,
    )

    async with Client(server) as client:
        result = await client.call_tool("search_catalog", {"query": "méthode"})

    assert result.is_error is False
    assert result.structured_content["items"] == []


@pytest.mark.asyncio
async def test_registry_server_advertises_only_tools_in_token_scopes() -> None:
    token = access_token()
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    async with Client(server) as client:
        listed = await client.list_tools()

    assert {item.name for item in listed.tools} == {
        "search_catalog",
        "get_artifact",
        "list_updates",
        "get_operation",
    }


class AcceptingMcpTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        return access_token() if token == "valid-token" else None


class InstallBackend(SearchBackend):
    async def request_install(self, request: RequestInstallInput) -> InstallationPlan:
        return build_installation_plan(
            release_id=request.release_id,
            artifact_id=UUID("11111111-1111-4111-8111-111111111111"),
            artifact_type=ArtifactType.SKILL,
            artifact_slug="business-method",
            version="1.0.0",
            profile=request.profile,
            scope=request.scope,
            target=request.target,
            package_locator="https://packages.kya.energy/business-method.zip",
            content_digest="b" * 64,
            compatibility_requirement=">=2026-09",
            client_version=request.client_version,
            file_count=3,
            package_size=1024,
        )


@pytest.mark.asyncio
async def test_registry_server_returns_a_consent_bound_installation_plan() -> None:
    token = AccessToken(
        token="opaque-install-token",
        client_id="codex-test",
        subject="alice",
        scopes=["catalog:install"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )
    server = create_registry_server(
        backend=InstallBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    release_id = UUID("01991b00-0000-7000-8000-000000000301")
    async with Client(server) as client:
        result = await client.call_tool(
            "request_install",
            {
                "release_id": str(release_id),
                "target": "workspace:dss",
                "profile": "codex",
                "scope": "personal",
                "client_version": "2026-09",
                "idempotency_key": "install-business-method-0001",
                "confirmation": {"confirmed": True},
            },
        )

    assert result.is_error is False
    assert result.structured_content["release_id"] == str(release_id)
    assert result.structured_content["requires_client_confirmation"] is True
    assert result.structured_content["server_writes_local_files"] is False
    assert len(result.structured_content["steps"]) == 7


@pytest.mark.asyncio
async def test_registry_server_records_a_client_installation_receipt() -> None:
    principal = "01991e00-0000-7000-8000-000000000003"
    token = AccessToken(
        token="opaque-install-token",
        client_id="codex-test",
        subject=principal,
        scopes=["catalog:install"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "confirm_installation",
            {
                "plan_id": "01991e00-0000-7000-8000-000000000010",
                "release_id": "01991e00-0000-7000-8000-000000000011",
                "target": "workspace:dss",
                "profile": "codex",
                "scope": "personal",
                "client_version": "2026-09",
                "installed_digest": "b" * 64,
                "idempotency_key": "confirm-installation-mcp-0001",
                "confirmation": {"confirmed": True},
            },
        )

    assert result.is_error is False
    assert result.structured_content["status"] == "active"


def test_registry_http_uses_2026_stateless_request_metadata() -> None:
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=AcceptingMcpTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
    )
    transport = server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["testserver"],
        ),
    )
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {
                    "name": "kya-contract-test",
                    "version": "1",
                },
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    }

    with TestClient(transport, follow_redirects=False) as client:
        response = client.post(
            "/",
            headers={
                "Authorization": "Bearer valid-token",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            json=request,
        )
        unauthenticated = client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            json=request,
        )
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    assert {item["name"] for item in response.json()["result"]["tools"]} == {
        "search_catalog",
        "get_artifact",
        "list_updates",
        "get_operation",
    }
    assert unauthenticated.status_code == 401
    assert "resource_metadata=" in unauthenticated.headers["WWW-Authenticate"]
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://registry.example.test/mcp"
    assert metadata.json()["scopes_supported"] == ["catalog:read"]
