"""MCP profile HTTP routes expose live grants and restrictive preferences."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.config import Settings
from kya_platform.main import create_app

PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")


def principal() -> AuthorizedPrincipal:
    return AuthorizedPrincipal(
        PRINCIPAL_ID,
        AuthenticatedIdentity("https://issuer.test", "subject", {}),
        "direction-cvsi",
    )


def app_client() -> tuple[TestClient, object, object]:
    app = create_app(Settings(_env_file=None, environment="test"))
    app.dependency_overrides[active_principal] = principal
    broker = AsyncMock()
    broker.get_active_grant_scopes.return_value = frozenset({"data:read"})
    runtime = AsyncMock()
    runtime.resolve.return_value = SimpleNamespace(
        effective_tool_keys=("search_data_assets",),
        revision="a" * 64,
        diverged=True,
    )
    preferences = AsyncMock()
    preferences.disable_tool.return_value = 1
    app.state.oauth_broker = broker
    app.state.mcp_tool_profile_runtime = runtime
    app.state.mcp_preference_service = preferences
    return TestClient(app), runtime, preferences


def test_reads_effective_profile_from_the_live_connector_grant() -> None:
    client, runtime, _preferences = app_client()
    with client:
        response = client.get("/api/v1/mcp/me/effective-profile?client_id=claude")

    assert response.status_code == 200
    assert response.json()["tool_keys"] == ["search_data_assets"]
    assert response.json()["shadow_diverged"] is True
    request = runtime.resolve.await_args.args[0]  # type: ignore[attr-defined]
    assert request.oauth_scopes == frozenset({"data:read"})


def test_disables_then_restores_a_tool_with_optimistic_revision() -> None:
    client, _runtime, preferences = app_client()
    with client:
        disabled = client.put(
            "/api/v1/mcp/me/tool-preferences/search_data_assets",
            json={"expected_revision": 0, "client_id": "claude"},
        )
        inherited = client.delete(
            "/api/v1/mcp/me/tool-preferences/search_data_assets"
            "?expected_revision=1&client_id=claude"
        )

    assert disabled.status_code == 200
    assert disabled.json() == {
        "tool_key": "search_data_assets",
        "state": "disabled",
        "revision": 1,
    }
    assert inherited.status_code == 204
    assert preferences.disable_tool.await_count == 1  # type: ignore[attr-defined]
    assert preferences.inherit_tool.await_count == 1  # type: ignore[attr-defined]


def test_missing_connector_grant_is_not_simulated_from_user_input() -> None:
    client, _runtime, _preferences = app_client()
    client.app.state.oauth_broker.get_active_grant_scopes.return_value = None
    with client:
        response = client.get("/api/v1/mcp/me/effective-profile?client_id=unknown")
    assert response.status_code == 404
    assert response.json()["code"] == "mcp_connector_not_found"
