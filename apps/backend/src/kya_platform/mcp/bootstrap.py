"""Public, read-only MCP surface used to verify client connectivity safely."""

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel


class FoundationStatus(BaseModel):
    environment: str
    api: str
    identity: str
    authorization: str
    database: str
    registry_access: str


def create_bootstrap_server(*, environment: str) -> MCPServer[None]:
    """Expose no sensitive data and no mutation before individual OAuth is connected."""

    server: MCPServer[None] = MCPServer(
        "kya-bootstrap",
        title="KYA Platform — Connexion",
        description="Vérification publique et non sensible du canal MCP KYA",
        instructions=(
            "Ce serveur confirme la connectivité. Le catalogue interne et les actions "
            "restent sur le Registry MCP authentifié et autorisé par rôle."
        ),
        version="0.1.0-dev.11",
    )

    @server.tool(name="get_foundation_status", structured_output=True)
    async def get_foundation_status() -> FoundationStatus:
        """Vérifier que les fondations KYA sont disponibles, sans lire de donnée métier."""

        return FoundationStatus(
            environment=environment,
            api="available",
            identity="neon-auth-ready",
            authorization="openfga-ready",
            database="neon-ready",
            registry_access="authentication-required",
        )

    @server.tool(name="get_next_step", structured_output=True)
    async def get_next_step() -> dict[str, str]:
        """Indiquer l'étape sûre après le test de transport MCP."""

        return {
            "step": "sign-in-to-kya-platform",
            "purpose": "link-a-kya-principal-before-private-registry-access",
        }

    return server


__all__ = ["FoundationStatus", "create_bootstrap_server"]
