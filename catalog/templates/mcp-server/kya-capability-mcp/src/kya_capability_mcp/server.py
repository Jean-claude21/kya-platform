"""Thin MCP delivery layer for one governed KYA capability."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from kya_capability_mcp.service import CapabilityService, DemoCapabilityBackend

server = MCPServer(
    "KYA Capability",
    instructions="Expose only data already authorized for the active KYA context.",
)
service = CapabilityService(DemoCapabilityBackend())


@server.tool()
async def find_records(
    query: Annotated[str, Field(min_length=2, max_length=200)],
    ctx: Context,
) -> dict[str, object]:
    """Find authorized records matching a precise business query."""

    await ctx.info("Authorized capability query started")
    result = await service.find_records(query)
    return result.model_dump()


def main() -> None:
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
