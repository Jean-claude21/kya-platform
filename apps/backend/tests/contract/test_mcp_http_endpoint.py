"""Remote MCP clients can use the documented URL with or without trailing slash."""

import pytest
from fastapi.testclient import TestClient

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
