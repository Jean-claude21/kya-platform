from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.authorization.service import AuthorizationService
from kya_platform.mcp.registry import (
    ArtifactDetail,
    ArtifactSummary,
    Confirmation,
    RequestInstallInput,
    SearchCatalogInput,
    SearchCatalogOutput,
    ToolAccessContext,
    ToolAuthorizer,
)
from kya_platform.mcp.registry.contracts import REGISTRY_TOOLS
from kya_platform.mcp.registry.server import create_registry_server


@dataclass
class RecordingPolicy:
    allowed: bool
    checks: list[CheckRequest]

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(allowed=self.allowed, model_id="test-model")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return ()


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
        idempotency_key="install-request-0001",
        confirmation=Confirmation(confirmed=True),
    )
    assert request.confirmation.confirmed is True


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
    assert policy.checks[0].relation == "can_install"


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
    async def search_catalog(self, request: SearchCatalogInput) -> SearchCatalogOutput:
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

    async def get_artifact(self, request: Any) -> ArtifactDetail:
        raise AssertionError("not called")

    async def list_updates(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def request_install(self, request: Any) -> Any:
        raise AssertionError("not called")

    async def request_update(self, request: Any) -> Any:
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
    assert policy.checks[0].user == "user:alice"


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

    assert result.is_error is True
    assert "not_authorized" in str(result.content)
