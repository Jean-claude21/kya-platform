"""OAuth-protected Registry MCP server over Streamable HTTP."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.routes import create_protected_resource_routes
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.reliability import JsonValue
from kya_platform.authorization import AuthorizationService, ContextualTuple
from kya_platform.authorization.model import active_unit_context
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.mcp.data.contracts import DATA_TOOLS
from kya_platform.mcp.registry.contracts import (
    REGISTRY_TOOLS,
    ArtifactDetail,
    Confirmation,
    ConfirmInstallationInput,
    ConfirmUpdateInput,
    GetArtifactInput,
    GetOperationInput,
    InstallationAction,
    InstallationPlan,
    InstallationProfile,
    InstallationRecorded,
    InstallationScope,
    ListUpdatesInput,
    ListUpdatesOutput,
    ManageInstallationInput,
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

if TYPE_CHECKING:
    from kya_platform.mcp.data.server import DataMcpAuditSink, DataMcpBackend

type AccessTokenProvider = Callable[[], AccessToken | None]
type ToolVisibility = Callable[[str], Awaitable[bool]]
type ToolSetProvider = Callable[[], Awaitable[frozenset[str]]]
ALL_TOOLS = REGISTRY_TOOLS + DATA_TOOLS
SUPPORTED_SCOPES = sorted({item.oauth_scope for item in ALL_TOOLS})


class RegistryBackend(Protocol):
    async def search_catalog(
        self, request: SearchCatalogInput, *, allowed_ids: tuple[str, ...]
    ) -> SearchCatalogOutput: ...

    async def resolve_artifact_id(self, public_id: str) -> UUID | None: ...

    async def resolve_installation_workspace(self, installation_id: UUID) -> str | None: ...

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None: ...

    async def get_artifact(self, request: GetArtifactInput) -> ArtifactDetail: ...

    async def list_updates(self, request: ListUpdatesInput) -> ListUpdatesOutput: ...

    async def request_install(self, request: RequestInstallInput) -> InstallationPlan: ...

    async def confirm_installation(
        self, request: ConfirmInstallationInput
    ) -> InstallationRecorded: ...

    async def request_update(self, request: RequestUpdateInput) -> OperationAccepted: ...

    async def confirm_update(self, request: ConfirmUpdateInput) -> OperationStatus: ...

    async def manage_installation(self, request: ManageInstallationInput) -> OperationStatus: ...

    async def get_operation(self, request: GetOperationInput) -> OperationStatus: ...

    async def publish_candidate(self, request: PublishCandidateInput) -> PublicationAccepted: ...


class ScopedRegistryServer(MCPServer[None]):
    """Advertise only tools covered by the caller's OAuth scopes."""

    def __init__(
        self,
        *args: object,
        access_token_provider: AccessTokenProvider,
        tool_visibility: ToolVisibility | None = None,
        tool_set_provider: ToolSetProvider | None = None,
        **kwargs: object,
    ):
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._access_token_provider = access_token_provider
        self._tool_visibility = tool_visibility
        self._tool_set_provider = tool_set_provider

    async def list_tools(self):  # type: ignore[no-untyped-def]
        token = self._access_token_provider()
        if token is None:
            return []
        permitted = {item.name for item in ALL_TOOLS if item.oauth_scope in token.scopes}
        tools = [tool for tool in await super().list_tools() if tool.name in permitted]
        if self._tool_set_provider is not None:
            governed = await self._tool_set_provider()
            return [tool for tool in tools if tool.name in governed]
        if self._tool_visibility is None:
            return tools
        return [tool for tool in tools if await self._tool_visibility(tool.name)]

    def streamable_http_app(self, **kwargs: object):  # type: ignore[no-untyped-def]
        """Advertise optional scopes while enforcing each one at tool invocation."""
        app = super().streamable_http_app(**kwargs)  # type: ignore[arg-type]
        auth = self.settings.auth
        if auth is None or auth.resource_server_url is None:
            return app
        metadata_routes = create_protected_resource_routes(
            resource_url=auth.resource_server_url,
            authorization_servers=[auth.issuer_url],
            scopes_supported=SUPPORTED_SCOPES,
            resource_name="KYA Platform MCP",
        )
        metadata_paths = {route.path for route in metadata_routes}
        app.routes[:] = [
            route for route in app.routes if getattr(route, "path", None) not in metadata_paths
        ]
        app.routes.extend(metadata_routes)
        return app


def _tool(name: str):  # type: ignore[no-untyped-def]
    return next(item for item in ALL_TOOLS if item.name == name)


class RegistryGuard:
    def __init__(
        self,
        authorization: AuthorizationService,
        access_token_provider: AccessTokenProvider,
        tool_set_provider: ToolSetProvider | None = None,
    ) -> None:
        self._authorizer = ToolAuthorizer(authorization)
        self._access_token_provider = access_token_provider
        self._tool_set_provider = tool_set_provider

    async def _require_profile(self, name: str) -> None:
        if self._tool_set_provider is not None and name not in await self._tool_set_provider():
            raise ToolError("tool_profile_required")

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
        await self._require_profile(name)
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

    async def is_visible(self, name: str) -> bool:
        """Hide Data tools unless the active unit grants their required relation."""
        if name not in {item.name for item in DATA_TOOLS}:
            return True
        try:
            token = self._token(name)
            context, contextual_tuples = self._active_context(token)
            active_unit = self.active_unit(name)
            return await self._authorizer.is_allowed(
                _tool(name),
                ToolAccessContext(
                    self._principal(token),
                    frozenset(token.scopes),
                    active_unit,
                    context,
                    contextual_tuples,
                ),
            )
        except ToolError:
            return False

    def active_unit(self, name: str) -> str:
        token = self._token(name)
        claims = token.claims or {}
        active_unit = claims.get("active_unit")
        if not isinstance(active_unit, str) or not active_unit:
            raise ToolError("active_unit_required")
        return active_unit

    def principal_id(self, name: str) -> UUID:
        principal = self._principal(self._token(name)).removeprefix("user:")
        try:
            return UUID(principal)
        except ValueError as error:
            raise ToolError("principal_identifier_invalid") from error

    async def allowed_artifact_ids(self, name: str) -> tuple[str, ...]:
        token = self._token(name)
        await self._require_profile(name)
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
    data_backend: DataMcpBackend | None = None,
    data_audit: DataMcpAuditSink | None = None,
    tool_set_provider: ToolSetProvider | None = None,
) -> MCPServer[None]:
    """Build the remote server; OAuth authenticates and KYA policy authorizes."""

    guard = RegistryGuard(authorization, access_token_provider, tool_set_provider)
    server: MCPServer[None] = ScopedRegistryServer(
        "kya-platform",
        title="KYA Platform MCP",
        description="Capacités et données gouvernées de KYA-Energy Group",
        version="0.2.0",
        token_verifier=token_verifier,
        access_token_provider=access_token_provider,
        tool_visibility=guard.is_visible,
        tool_set_provider=tool_set_provider,
        auth=AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_url,
            required_scopes=[],
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
    async def list_updates(installation_id: UUID) -> ListUpdatesOutput:
        """Lister les mises à jour compatibles et autorisées."""
        workspace = await backend.resolve_installation_workspace(installation_id)
        if workspace is None:
            raise ToolError("installation_not_found")
        await guard.require("list_updates", workspace)
        return await backend.list_updates(ListUpdatesInput(installation_id=installation_id))

    @server.tool(name="request_install", structured_output=True)
    async def request_install(
        release_id: UUID,
        target: str,
        profile: InstallationProfile,
        scope: InstallationScope,
        client_version: str,
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> InstallationPlan:
        """Résoudre un plan déterministe ; le client garde la décision d'écriture."""
        target_id = target.removeprefix("workspace:")
        await guard.require("request_install", target_id)
        return await backend.request_install(
            RequestInstallInput(
                release_id=release_id,
                target=target,
                profile=profile,
                scope=scope,
                client_version=client_version,
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
        workspace = await backend.resolve_installation_workspace(installation_id)
        if workspace is None:
            raise ToolError("installation_not_found")
        await guard.require("request_update", workspace)
        return await backend.request_update(
            RequestUpdateInput(
                installation_id=installation_id,
                release_id=release_id,
                actor_id=guard.principal_id("request_update"),
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

    @server.tool(name="confirm_installation", structured_output=True)
    async def confirm_installation(
        plan_id: UUID,
        release_id: UUID,
        target: str,
        profile: InstallationProfile,
        scope: InstallationScope,
        client_version: str,
        installed_digest: str,
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> InstallationRecorded:
        """Enregistrer le reçu client après vérification et activation locales."""
        target_id = target.removeprefix("workspace:")
        await guard.require("confirm_installation", target_id)
        return await backend.confirm_installation(
            ConfirmInstallationInput(
                plan_id=plan_id,
                release_id=release_id,
                target=target,
                profile=profile,
                scope=scope,
                client_version=client_version,
                installed_digest=installed_digest,
                actor_id=guard.principal_id("confirm_installation"),
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

    @server.tool(name="confirm_update", structured_output=True)
    async def confirm_update(
        operation_id: UUID,
        installed_digest: str,
        expected_revision: int,
        confirmation: Confirmation,
    ) -> OperationStatus:
        """Finaliser une mise à jour uniquement après le reçu vérifié du client."""
        workspace = await backend.resolve_operation_workspace(operation_id)
        if workspace is None:
            raise ToolError("operation_not_found")
        await guard.require("confirm_update", workspace)
        return await backend.confirm_update(
            ConfirmUpdateInput(
                operation_id=operation_id,
                installed_digest=installed_digest,
                expected_revision=expected_revision,
                actor_id=guard.principal_id("confirm_update"),
                confirmation=confirmation,
            )
        )

    @server.tool(name="get_operation", structured_output=True)
    async def get_operation(operation_id: UUID) -> OperationStatus:
        """Consulter l'état et la preuve d'une opération visible."""
        workspace = await backend.resolve_operation_workspace(operation_id)
        if workspace is None:
            raise ToolError("operation_not_found")
        await guard.require("get_operation", workspace)
        return await backend.get_operation(GetOperationInput(operation_id=operation_id))

    @server.tool(name="manage_installation", structured_output=True)
    async def manage_installation(
        installation_id: UUID,
        action: InstallationAction,
        expected_revision: int,
        idempotency_key: str,
        confirmation: Confirmation,
        reason: str | None = None,
    ) -> OperationStatus:
        """Suspendre, reprendre, révoquer ou restaurer une installation avec preuve."""
        workspace = await backend.resolve_installation_workspace(installation_id)
        if workspace is None:
            raise ToolError("installation_not_found")
        await guard.require("manage_installation", workspace)
        return await backend.manage_installation(
            ManageInstallationInput(
                installation_id=installation_id,
                action=action,
                expected_revision=expected_revision,
                actor_id=guard.principal_id("manage_installation"),
                reason=reason,
                idempotency_key=idempotency_key,
                confirmation=confirmation,
            )
        )

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

    if (data_backend is None) != (data_audit is None):
        raise ValueError("Data MCP backend and audit sink must be configured together")
    if data_backend is not None and data_audit is not None:
        from kya_platform.mcp.data.server import register_data_tools

        register_data_tools(server, backend=data_backend, guard=guard, audit=data_audit)

    return server


__all__ = ["RegistryBackend", "RegistryGuard", "create_registry_server"]
