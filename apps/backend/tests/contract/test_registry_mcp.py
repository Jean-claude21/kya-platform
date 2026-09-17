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
    ArtifactProposalAccepted,
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


def test_catalog_search_accepts_listing_and_single_character_queries() -> None:
    assert SearchCatalogInput().query == ""
    assert SearchCatalogInput(query="e").query == "e"


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

    async def resolve_release_workspace(self, release_id: UUID) -> str | None:
        return "dss"

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None:
        return "dss"

    async def resolve_installable_release_id(
        self, *, artifact_id: str, version: str | None, profile: Any
    ) -> UUID | None:
        return UUID("01991b00-0000-7000-8000-000000000302")

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


class DetailBackend(SearchBackend):
    async def get_artifact(self, request: Any) -> ArtifactDetail:
        return ArtifactDetail(
            artifact_id="kya:skill:business-method",
            artifact_type="skill",
            name="Méthode métier KYA",
            latest_version="0.1.0",
            versions=("0.1.0",),
            installable=True,
        )


def access_token() -> AccessToken:
    return AccessToken(
        token="opaque-test-token",
        client_id="codex-test",
        subject="alice",
        scopes=["catalog:read"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )


@pytest.mark.asyncio
async def test_get_artifact_keeps_its_backward_compatible_output_schema() -> None:
    server = create_registry_server(
        backend=DetailBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=access_token,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "get_artifact", {"artifact_id": "kya:skill:business-method", "version": "0.1.0"}
        )

    assert result.is_error is False
    assert result.structured_content["installable"] is True
    assert "installable_releases" not in result.structured_content


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
async def test_registry_server_lists_authorized_catalog_without_query() -> None:
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
        result = await client.call_tool("search_catalog", {"types": ["skill"]})

    assert result.is_error is False
    assert result.structured_content["items"][0]["effective_permissions"] == ["view"]


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


@pytest.mark.asyncio
async def test_registry_server_applies_one_governed_set_to_list_and_direct_call() -> None:
    calls = 0

    async def governed_tools() -> frozenset[str]:
        nonlocal calls
        calls += 1
        return frozenset({"get_artifact"})

    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=access_token,
        tool_set_provider=governed_tools,
    )

    async with Client(server) as client:
        listed = await client.list_tools()
        denied = await client.call_tool("search_catalog", {"query": "méthode"})

    assert {item.name for item in listed.tools} == {"get_artifact"}
    assert denied.is_error
    assert calls == 2


class AcceptingMcpTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        return access_token() if token == "valid-token" else None


class InstallBackend(SearchBackend):
    last_request: RequestInstallInput | None = None

    async def request_install(self, request: RequestInstallInput) -> InstallationPlan:
        self.last_request = request
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


class ProposalBackend:
    last_request: Any = None

    async def resolve_workspace_id(self, workspace_key: str) -> UUID | None:
        assert workspace_key == "dss"
        return UUID("01991e00-0000-7000-8000-000000000071")

    async def submit_artifact_proposal(self, request: Any, **context: Any) -> Any:
        self.last_request = request, context
        return ArtifactProposalAccepted(proposal_id=UUID("01991e00-0000-7000-8000-000000000081"))


@pytest.mark.asyncio
async def test_registry_server_submits_an_application_proposal_with_safe_defaults() -> None:
    principal = "01991e00-0000-7000-8000-000000000003"
    token = AccessToken(
        token="opaque-publish-token",
        client_id="claude-ai",
        subject=principal,
        scopes=["catalog:publish"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )
    proposals = ProposalBackend()
    policy = RecordingPolicy(allowed=True, checks=[])
    server = create_registry_server(
        backend=SearchBackend(),
        authorization=AuthorizationService(policy),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
        proposal_backend=proposals,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "submit_artifact_proposal",
            {
                "target_workspace": "dss",
                "slug": "solar-operations",
                "artifact_type": "app",
                "files": [
                    {
                        "path": "artifact.manifest.json",
                        "kind": "manifest",
                        "content": "{}",
                    },
                    {"path": "package.json", "kind": "metadata", "content": "{}"},
                ],
            },
        )

    assert result.is_error is False
    assert result.structured_content == {
        "proposal_id": "01991e00-0000-7000-8000-000000000081",
        "status": "submitted",
        "review_required": True,
    }
    assert policy.checks[0].relation == "can_propose"
    assert policy.checks[0].object == "workspace:dss"
    assert proposals.last_request is not None
    request, context = proposals.last_request
    assert request.confirmation.confirmed is True
    assert request.idempotency_key.startswith("proposal:")
    assert context["actor_id"] == UUID(principal)


@pytest.mark.asyncio
async def test_registry_server_returns_a_consent_bound_installation_plan() -> None:
    token = AccessToken(
        token="opaque-install-token",
        client_id="codex-test",
        subject="alice",
        scopes=["catalog:install"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )
    backend = InstallBackend()
    server = create_registry_server(
        backend=backend,
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    async with Client(server) as client:
        listed = await client.list_tools()
        result = await client.call_tool(
            "request_install",
            {"artifact_id": "kya:skill:business-method"},
        )

    install_tool = next(item for item in listed.tools if item.name == "request_install")
    assert install_tool.input_schema.get("required", []) == []
    assert result.is_error is False
    assert result.structured_content["release_id"] == "01991b00-0000-7000-8000-000000000302"
    assert result.structured_content["requires_client_confirmation"] is True
    assert result.structured_content["server_writes_local_files"] is False
    assert len(result.structured_content["steps"]) == 7
    assert backend.last_request is not None
    assert backend.last_request.profile.value == "claude-code"
    assert backend.last_request.scope.value == "personal"
    assert backend.last_request.target == "workspace:dss"


@pytest.mark.asyncio
async def test_registry_server_accepts_a_cached_legacy_release_id_schema() -> None:
    token = AccessToken(
        token="opaque-install-token",
        client_id="claude-cached",
        subject="alice",
        scopes=["catalog:install"],
        claims={"active_unit": "dss", "iss": "https://auth.example.test"},
    )
    backend = InstallBackend()
    server = create_registry_server(
        backend=backend,
        authorization=AuthorizationService(RecordingPolicy(allowed=True, checks=[])),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    release_id = "01991b00-0000-7000-8000-000000000302"
    async with Client(server) as client:
        result = await client.call_tool(
            "request_install",
            {
                "release_id": release_id,
                "profile": "claude-code",
                "scope": "personal",
                "target": "workspace:dss",
                "client_version": "2026-09",
                "idempotency_key": "claude-cached-install-0001",
                "confirmation": {"confirmed": True},
            },
        )

    assert result.is_error is False
    assert backend.last_request is not None
    assert str(backend.last_request.release_id) == release_id


@pytest.mark.asyncio
async def test_registry_server_maps_active_org_unit_to_release_workspace() -> None:
    token = AccessToken(
        token="opaque-install-token",
        client_id="claude-current",
        subject="alice",
        scopes=["catalog:install"],
        claims={"active_unit": "group", "iss": "https://auth.example.test"},
    )
    backend = InstallBackend()
    workspace_id = "22222222-2222-4222-8222-222222222222"

    async def release_workspace(_release_id: UUID) -> str:
        return workspace_id

    backend.resolve_release_workspace = release_workspace  # type: ignore[method-assign]
    policy = RecordingPolicy(allowed=True, checks=[])
    server = create_registry_server(
        backend=backend,
        authorization=AuthorizationService(policy),
        token_verifier=NoopTokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://registry.example.test/mcp",
        access_token_provider=lambda: token,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "request_install",
            {
                "artifact_id": "kya:skill:business-method",
                "target": "workspace:group",
            },
        )

    assert result.is_error is False
    assert backend.last_request is not None
    assert backend.last_request.target == f"workspace:{workspace_id}"
    assert policy.checks[0].object == f"workspace:{workspace_id}"


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
    assert metadata.json()["scopes_supported"] == [
        "catalog:install",
        "catalog:publish",
        "catalog:read",
        "data:content:read",
        "data:ingest",
        "data:read",
    ]
