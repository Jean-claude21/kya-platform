"""One capability per tool; authorization is checked before business execution."""

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

server = MCPServer(
    "KYA Capability",
    instructions="Expose only data already authorized for the active KYA context.",
)


@server.tool()
async def find_records(
    query: Annotated[str, Field(min_length=2, max_length=200)],
    ctx: Context,
) -> dict[str, object]:
    """Find authorized records matching a precise business query."""

    # Replace with a Business API call carrying the verified principal and active KYA context.
    await ctx.info("Authorized capability query started")
    return {"query": query, "items": [], "is_demo": True}


if __name__ == "__main__":
    server.run(transport="streamable-http")
