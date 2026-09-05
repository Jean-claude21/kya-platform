"""The bootstrap MCP stays public, read-only and non-sensitive."""

import pytest
from mcp import Client

from kya_platform.mcp.bootstrap import create_bootstrap_server


@pytest.mark.asyncio
async def test_bootstrap_mcp_exposes_only_safe_connectivity_tools() -> None:
    server = create_bootstrap_server(environment="preview")

    async with Client(server) as client:
        tools = await client.list_tools()
        status = await client.call_tool("get_foundation_status", {})

    assert {tool.name for tool in tools.tools} == {"get_foundation_status", "get_next_step"}
    assert status.structured_content == {
        "environment": "preview",
        "api": "available",
        "identity": "neon-auth-ready",
        "authorization": "openfga-ready",
        "database": "neon-ready",
        "registry_access": "authentication-required",
    }
