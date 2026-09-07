"""Late-bound MCP adapters fail closed and delegate only after startup."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import CheckRequest, ListObjectsRequest
from kya_platform.mcp.registry.runtime import (
    StateAuthorizationPort,
    StateIdentityMapping,
    StateRegistryBackend,
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
async def test_state_registry_backend_fails_closed_then_delegates_every_operation() -> None:
    state = State()
    state.registry_mcp_backend = None
    adapter = StateRegistryBackend(state)
    with pytest.raises(ToolError, match="registry_unavailable"):
        await adapter.resolve_artifact_id("kya:skill:test")

    backend = AsyncMock()
    backend.search_catalog.return_value = "search"
    backend.resolve_artifact_id.return_value = "resolve"
    backend.get_artifact.return_value = "get"
    backend.list_updates.return_value = "updates"
    backend.request_install.return_value = "install"
    backend.request_update.return_value = "update"
    backend.get_operation.return_value = "operation"
    backend.publish_candidate.return_value = "publish"
    state.registry_mcp_backend = backend

    assert await adapter.search_catalog("request", allowed_ids=()) == "search"
    assert await adapter.resolve_artifact_id("id") == "resolve"
    assert await adapter.get_artifact("request") == "get"
    assert await adapter.list_updates("request") == "updates"
    assert await adapter.request_install("request") == "install"
    assert await adapter.request_update("request") == "update"
    assert await adapter.get_operation("request") == "operation"
    assert await adapter.publish_candidate("request") == "publish"
