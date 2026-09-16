"""Remote MCP clients can use the documented URL with or without trailing slash."""

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kya_platform.config import Settings
from kya_platform.main import create_app

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "connector-probe", "version": "1"},
    },
}


@pytest.mark.contract
@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_mcp_connector_url_initializes_without_redirect(path: str) -> None:
    application = create_app(
        Settings(
            _env_file=None,
            environment="preview",
            mcp_allowed_hosts=("testserver",),
        )
    )
    with TestClient(application, follow_redirects=False) as client:
        response = client.post(
            path,
            headers={"Accept": "application/json, text/event-stream"},
            json=INITIALIZE,
        )

    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.json()["result"]["serverInfo"]["name"] == "kya-bootstrap"


def test_protected_registry_routes_are_mounted_separately() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=SecretStr("postgresql+asyncpg://test:test@localhost/test"),
            neon_auth_issuer="https://auth.example.test",
            neon_auth_jwks_url="https://auth.example.test/.well-known/jwks.json",
            neon_auth_audience="https://auth.example.test",
            openfga_api_url="https://fga.example.test",
            openfga_api_token=SecretStr("test-token"),
            openfga_store_id="test-store",
            openfga_model_id="test-model",
            registry_mcp_enabled=True,
            registry_mcp_authorization_server_url="https://api.example.test",
            registry_mcp_resource_url="https://registry.example.test/mcp",
            oauth_broker_enabled=True,
            oauth_issuer_url="https://api.example.test",
            oauth_consent_url="https://app.example.test/oauth/consent",
            oauth_client_secret_key=SecretStr(Fernet.generate_key().decode()),
        )
    )

    paths = {getattr(route, "path", None) for route in application.router.routes}
    assert "/mcp" in paths
    assert "/registry/mcp" in paths
    assert "/registry/mcp/" in paths
    assert "/.well-known/oauth-protected-resource/registry/mcp" in paths
    assert "/.well-known/oauth-authorization-server" in paths
    assert "/authorize" in paths
    assert "/token" in paths
    assert "/register" in paths
    assert "/revoke" in paths
