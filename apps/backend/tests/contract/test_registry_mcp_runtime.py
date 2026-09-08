"""Late-bound MCP adapters fail closed and delegate only after startup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import CheckRequest, ListObjectsRequest
from kya_platform.mcp.registry.runtime import (
    StateAuthorizationPort,
    StateDataMcpAuditSink,
    StateDataMcpBackend,
    StateIdentityMapping,
    StateRegistryBackend,
    StateToolSetProvider,
)


@pytest.mark.asyncio
async def test_state_identity_mapping_is_unavailable_then_delegates() -> None:
    state = State()
    state.identity_mapping = None
    adapter = StateIdentityMapping(state)
    identity = AuthenticatedIdentity("https://issuer.test", "subject", {})

    assert await adapter.resolve_principal_id(identity) is None

    expected = UUID("11111111-1111-4111-8111-111111111111")
    mapping = AsyncMock()
    mapping.resolve_principal_id.return_value = expected
    state.identity_mapping = mapping
    assert await adapter.resolve_principal_id(identity) == expected


@pytest.mark.asyncio
async def test_state_authorization_fails_closed_then_delegates() -> None:
    state = State()
    state.authorization = None
    adapter = StateAuthorizationPort(state)
    check = CheckRequest(user="user:alice", relation="can_view", object="artifact:one")
    listing = ListObjectsRequest(user="user:alice", relation="can_view", object_type="artifact")

    assert (await adapter.check(check)).allowed is False
    assert await adapter.list_objects(listing) == ()

    authorization = AsyncMock()
    authorization.check.return_value = type("Decision", (), {"allowed": True})()
    authorization.list_objects.return_value = ("artifact:one",)
    state.authorization = authorization
    assert (await adapter.check(check)).allowed is True
    assert await adapter.list_objects(listing) == ("artifact:one",)


@pytest.mark.asyncio
async def test_state_tool_set_provider_fails_closed_and_builds_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = State()
    state.mcp_tool_profile_runtime = None
    provider = StateToolSetProvider(state)
    monkeypatch.setattr(
        "kya_platform.mcp.registry.runtime.get_access_token",
        lambda: None,
    )
    assert await provider() == frozenset()

    runtime = AsyncMock()
    runtime.resolve.return_value = SimpleNamespace(advertised_tool_keys=("data.find",))
    state.mcp_tool_profile_runtime = runtime
    token = AccessToken(
        token="opaque",
        client_id="claude",
        subject="11111111-1111-4111-8111-111111111111",
        scopes=["data:read"],
        claims={"active_unit": "direction-cvsi"},
    )
    monkeypatch.setattr(
        "kya_platform.mcp.registry.runtime.get_access_token",
        lambda: token,
    )
    assert await provider() == frozenset({"data.find"})
    request = runtime.resolve.await_args.args[0]
    assert request.client_id == "claude"
    assert request.active_unit_key == "direction-cvsi"


@pytest.mark.asyncio
async def test_state_tool_set_provider_rejects_invalid_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = State()
    state.mcp_tool_profile_runtime = AsyncMock()
    provider = StateToolSetProvider(state)
    token = AccessToken(
        token="opaque",
        client_id="claude",
        subject="not-a-uuid",
        scopes=["data:read"],
        claims={},
    )
    monkeypatch.setattr(
        "kya_platform.mcp.registry.runtime.get_access_token",
        lambda: token,
    )
    assert await provider() == frozenset()


@pytest.mark.asyncio
async def test_state_registry_backend_fails_closed_then_delegates_every_operation() -> None:
    state = State()
    state.registry_mcp_backend = None
    adapter = StateRegistryBackend(state)
    with pytest.raises(ToolError, match="registry_unavailable"):
        await adapter.resolve_artifact_id("kya:skill:test")

    backend = AsyncMock()
    backend.search_catalog.return_value = "search"
    backend.resolve_artifact_id.return_value = "resolve"
    backend.resolve_installation_workspace.return_value = "workspace"
    backend.resolve_operation_workspace.return_value = "workspace"
    backend.get_artifact.return_value = "get"
    backend.list_updates.return_value = "updates"
    backend.request_install.return_value = "install"
    backend.confirm_installation.return_value = "confirm"
    backend.request_update.return_value = "update"
    backend.confirm_update.return_value = "confirm-update"
    backend.manage_installation.return_value = "manage"
    backend.get_operation.return_value = "operation"
    backend.publish_candidate.return_value = "publish"
    state.registry_mcp_backend = backend

    assert await adapter.search_catalog("request", allowed_ids=()) == "search"
    assert await adapter.resolve_artifact_id("id") == "resolve"
    assert await adapter.resolve_installation_workspace("id") == "workspace"
    assert await adapter.resolve_operation_workspace("id") == "workspace"
    assert await adapter.get_artifact("request") == "get"
    assert await adapter.list_updates("request") == "updates"
    assert await adapter.request_install("request") == "install"
    assert await adapter.confirm_installation("request") == "confirm"
    assert await adapter.request_update("request") == "update"
    assert await adapter.confirm_update("request") == "confirm-update"
    assert await adapter.manage_installation("request") == "manage"
    assert await adapter.get_operation("request") == "operation"
    assert await adapter.publish_candidate("request") == "publish"


@pytest.mark.asyncio
async def test_state_data_backend_fails_closed_then_delegates() -> None:
    state = State()
    state.data_service = None
    adapter = StateDataMcpBackend(state)
    with pytest.raises(ToolError, match="data_service_unavailable"):
        await adapter.get_asset("direction-cvsi", "asset")

    service = AsyncMock()
    service.search_assets.return_value = "search"
    service.get_asset.return_value = "asset"
    service.get_contract.return_value = "contract"
    service.list_snapshots.return_value = "snapshots"
    service.trace_lineage.return_value = "lineage"
    service.get_pipeline.return_value = "pipeline"
    service.start_run.return_value = "run"
    state.data_service = service

    assert await adapter.search_assets("unit", "query", limit=2) == "search"
    assert await adapter.get_asset("unit", "asset") == "asset"
    assert await adapter.get_contract("unit", "asset") == "contract"
    assert await adapter.list_snapshots("unit", "asset", limit=2) == "snapshots"
    assert await adapter.trace_lineage("unit", "snapshot") == "lineage"
    assert await adapter.get_pipeline("unit", "pipeline") == "pipeline"
    assert await adapter.start_run("unit", "run", command="command") == "run"


@pytest.mark.asyncio
async def test_state_data_audit_is_append_only_and_fails_closed() -> None:
    state = State()
    state.audit_writer = None
    state.settings = SimpleNamespace(environment="test")
    audit = StateDataMcpAuditSink(state)
    with pytest.raises(ToolError, match="audit_unavailable"):
        await audit.ensure_available()

    writer = AsyncMock()
    state.audit_writer = writer
    await audit.ensure_available()
    correlation = UUID("01993480-0000-7000-8000-000000000099")
    actor = UUID("01993480-0000-7000-8000-000000000002")
    await audit.record(
        actor_id=actor,
        active_unit="direction-cvsi",
        tool_name="get_data_asset",
        target_type="data_asset",
        target_id="market-prices",
        decision="allowed",
        outcome="succeeded",
        correlation_id=correlation,
    )

    event = writer.append.await_args.args[0]
    assert event.actor_id == actor
    assert event.scope == "workspace:direction-cvsi"
    assert event.action == "mcp.get_data_asset"
    assert event.correlation_id == correlation
