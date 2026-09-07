"""OAuth-protected Registry MCP server over Streamable HTTP."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.reliability import JsonValue
from kya_platform.authorization import AuthorizationService, ContextualTuple
from kya_platform.authorization.model import active_unit_context
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.mcp.registry.contracts import (
    REGISTRY_TOOLS,
    ArtifactDetail,
    Confirmation,
    GetArtifactInput,
    GetOperationInput,
    ListUpdatesInput,
    ListUpdatesOutput,
    OperationAccepted,
    OperationStatus,
    PublicationAccepted,
    PublishCandidateInput,
    RequestInstallInput,
    RequestUpdateInput,
    SearchCatalogInput,
    SearchCatalogOutput,
    ToolAccessContext,
    ToolAuthorizer,
)

type AccessTokenProvider = Callable[[], AccessToken | None]


class RegistryBackend(Protocol):
    async def search_catalog(
        self, request: SearchCatalogInput, *, allowed_ids: tuple[str, ...]
    ) -> SearchCatalogOutput: ...

    async def resolve_artifact_id(self, public_id: str) -> UUID | None: ...

    async def get_artifact(self, request: GetArtifactInput) -> ArtifactDetail: ...

    async def list_updates(self, request: ListUpdatesInput) -> ListUpdatesOutput: ...

    async def request_install(self, request: RequestInstallInput) -> OperationAccepted: ...

    async def request_update(self, request: RequestUpdateInput) -> OperationAccepted: ...

    async def get_operation(self, request: GetOperationInput) -> OperationStatus: ...

    async def publish_candidate(self, request: PublishCandidateInput) -> PublicationAccepted: ...


class ScopedRegistryServer(MCPServer[None]):
    """Advertise only tools covered by the caller's OAuth scopes."""

    def __init__(self, *args: object, access_token_provider: AccessTokenProvider, **kwargs: object):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._access_token_provider = access_token_provider

    async def list_tools(self):  # type: ignore[no-untyped-def]
        token = self._access_token_provider()
        if token is None:
            return []
        permitted = {item.name for item in REGISTRY_TOOLS if item.oauth_scope in token.scopes}
        return [tool for tool in await super().list_tools() if tool.name in permitted]


def _tool(name: str):  # type: ignore[no-untyped-def]
    return next(item for item in REGISTRY_TOOLS if item.name == name)


class RegistryGuard:
    def __init__(
        self,
        authorization: AuthorizationService,
        access_token_provider: AccessTokenProvider,
    ) -> None:
        self._authorizer = ToolAuthorizer(authorization)
        self._access_token_provider = access_token_provider

    def _token(self, name: str) -> AccessToken:
        token = self._access_token_provider()
        if token is None:
            raise ToolError("authentication_required")
        if _tool(name).oauth_scope not in token.scopes:
            raise ToolError("scope_required")
        return token

    @staticmethod
    def _principal(token: AccessToken) -> str:
        subject = token.subject or token.client_id
        return subject if subject.startswith("user:") else f"user:{subject}"

    @staticmethod
    def _active_context(
        token: AccessToken,
    ) -> tuple[Mapping[str, JsonValue], tuple[ContextualTuple, ...]]:
        claims = token.claims or {}
        active_unit = claims.get("active_unit")
        if not isinstance(active_unit, str) or not active_unit:
            raise ToolError("active_unit_required")
        principal = RegistryGuard._principal(token).removeprefix("user:")
        return active_unit_context(
            user_id=principal,
            unit_id=active_unit,
            current_time=datetime.now(UTC),
        )

    async def require(self, name: str, resource: str) -> None:
        token = self._token(name)
        context, contextual_tuples = self._active_context(token)
        allowed = await self._authorizer.is_allowed(
            _tool(name),
            ToolAccessContext(
                self._principal(token),
                frozenset(token.scopes),
                resource,
                context,
                contextual_tuples,
            ),
        )
        if not allowed:
            raise ToolError("not_authorized")

    async def allowed_artifact_ids(self, name: str) -> tuple[str, ...]:
        token = self._token(name)
        context, contextual_tuples = self._active_context(token)
        return await self._authorizer.allowed_artifact_ids(
            ToolAccessContext(
                self._principal(token),
                frozenset(token.scopes),
                "catalog",
                context,
                contextual_tuples,
            )
        )


def create_registry_server(
    *,
    backend: RegistryBackend,
    authorization: AuthorizationService,
    token_verifier: TokenVerifier,
    issuer_url: str,
    resource_url: str,
    access_token_provider: AccessTokenProvider = get_access_token,
) -> MCPServer[None]:
    """Build the remote server; OAuth authenticates and KYA policy authorizes."""

    guard = RegistryGuard(authorization, access_token_provider)
    server: MCPServer[None] = ScopedRegistryServer(
        "kya-registry",
        title="KYA Registry MCP",
        description="Catalogue gouverné des capacités numériques KYA",
        version="0.1.0",
        token_verifier=token_verifier,
        access_token_provider=access_token_provider,
        auth=AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_url,
            required_scopes=["catalog:read"],
        ),
    )

    @server.tool(name="search_catalog", structured_output=True)
    async def search_catalog(
        query: str,
        types: list[ArtifactType] | None = None,
        workspace: str | None = None,
        cursor: str | None = None,
    ) -> SearchCatalogOutput:
        """Rechercher uniquement les artefacts que l'appelant peut découvrir."""
        allowed_ids = await guard.allowed_artifact_ids("search_catalog")
        return await backend.search_catalog(
            SearchCatalogInput(
                query=query,
                types=tuple(types or ()),
                workspace=workspace,
                cursor=cursor,
            ),
            allowed_ids=allowed_ids,
        )

    @server.tool(name="get_artifact", structured_output=True)
    async def get_artifact(artifact_id: str, version: str | None = None) -> ArtifactDetail:
        """Lire les métadonnées visibles d'un artefact, sans secret."""
        internal_id = await backend.resolve_artifact_id(artifact_id)
        if internal_id is None:
            raise ToolError("artifact_not_found")
        await guard.require("get_artifact", str(internal_id))
        return await backend.get_artifact(
            GetArtifactInput(artifact_id=artifact_id, version=version)
        )

    @server.tool(name="list_updates", structured_output=True)
    async def list_updates(
        environment: str | None = None, installation_id: UUID | None = None
    ) -> ListUpdatesOutput:
        """Lister les mises à jour compatibles et autorisées."""
        resource = str(installation_id) if installation_id else environment or "global"
        await guard.require("list_updates", resource)
        return await backend.list_updates(
            ListUpdatesInput(environment=environment, installation_id=installation_id)
        )

    @server.tool(name="request_install", structured_output=True)
    async def request_install(
        release_id: UUID,
        target: str,
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> OperationAccepted:
        """Créer une demande d'installation explicite et traçable."""
        target_id = target.removeprefix("workspace:")
        await guard.require("request_install", target_id)
        return await backend.request_install(
            RequestInstallInput(
                release_id=release_id,
                target=target,
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

    @server.tool(name="request_update", structured_output=True)
    async def request_update(
        installation_id: UUID,
        release_id: UUID,
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> OperationAccepted:
        """Demander une mise à jour soumise à la politique de revue."""
        await guard.require("request_update", str(installation_id))
        return await backend.request_update(
            RequestUpdateInput(
                installation_id=installation_id,
                release_id=release_id,
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

    @server.tool(name="get_operation", structured_output=True)
    async def get_operation(operation_id: UUID) -> OperationStatus:
        """Consulter l'état et la preuve d'une opération visible."""
        await guard.require("get_operation", str(operation_id))
        return await backend.get_operation(GetOperationInput(operation_id=operation_id))

    @server.tool(name="publish_candidate", structured_output=True)
    async def publish_candidate(
        artifact_id: str,
        version: str,
        evidence: list[str],
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> PublicationAccepted:
        """Soumettre un candidat à publication pour revue et approbation."""
        await guard.require("publish_candidate", artifact_id)
        return await backend.publish_candidate(
            PublishCandidateInput(
                artifact_id=artifact_id,
                version=version,
                evidence=tuple(evidence),
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

    return server


__all__ = ["RegistryBackend", "RegistryGuard", "create_registry_server"]
