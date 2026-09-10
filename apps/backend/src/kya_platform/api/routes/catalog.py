"""Permission-first HTTP discovery for governed capabilities."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.catalog import (
    CatalogBrowsePort,
    CatalogBrowseQuery,
    CatalogBrowseService,
    CatalogDetailPort,
    CatalogDetailService,
)
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.contracts.installation_plan import (
    InstallationPlan,
    InstallationProfile,
    InstallationScope,
)
from kya_platform.mcp.registry.contracts import (
    Confirmation,
    ConfirmInstallationInput,
    ConfirmUpdateInput,
    GetOperationInput,
    InstallationAction,
    InstallationRecorded,
    ListUpdatesInput,
    ListUpdatesOutput,
    ManageInstallationInput,
    OperationAccepted,
    OperationStatus,
    RequestInstallInput,
    RequestUpdateInput,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/catalog", tags=["catalog"])

ArtifactType = Literal["skill", "mcp", "app", "api", "dataset", "template"]


class CatalogSummaryResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    name: str
    summary: str | None
    latest_version: str
    lifecycle: str
    owner_workspace_id: str


class CatalogBrowseResponse(BaseModel):
    items: tuple[CatalogSummaryResponse, ...]
    active_unit: str
    has_more: bool


class CatalogDetailResponse(CatalogSummaryResponse):
    versions: tuple[str, ...]
    installable: bool
    risk: str
    source_repository: str
    content_digest: str


class CatalogBackend(CatalogBrowsePort, CatalogDetailPort, Protocol):
    async def resolve_release_id(self, public_id: str, version: str) -> UUID | None: ...

    async def resolve_installation_workspace(self, installation_id: UUID) -> str | None: ...

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None: ...

    async def request_install(self, request: RequestInstallInput) -> InstallationPlan: ...

    async def confirm_installation(
        self, request: ConfirmInstallationInput
    ) -> InstallationRecorded: ...

    async def list_updates(self, request: ListUpdatesInput) -> ListUpdatesOutput: ...

    async def request_update(self, request: RequestUpdateInput) -> OperationAccepted: ...

    async def confirm_update(self, request: ConfirmUpdateInput) -> OperationStatus: ...

    async def manage_installation(self, request: ManageInstallationInput) -> OperationStatus: ...

    async def get_operation(self, request: GetOperationInput) -> OperationStatus: ...


class InstallPlanRequest(BaseModel):
    version: str
    target: str
    profile: InstallationProfile
    scope: InstallationScope
    client_version: str
    confirmation: Confirmation


class InstallationReceiptRequest(BaseModel):
    plan_id: UUID
    release_id: UUID
    target: str
    profile: InstallationProfile
    scope: InstallationScope
    client_version: str
    installed_digest: str
    idempotency_key: str
    confirmation: Confirmation


class UpdateRequest(BaseModel):
    release_id: UUID
    idempotency_key: str
    confirmation: Confirmation


class UpdateReceiptRequest(BaseModel):
    installed_digest: str
    expected_revision: int
    confirmation: Confirmation


class InstallationActionRequest(BaseModel):
    action: InstallationAction
    expected_revision: int
    reason: str | None = None
    idempotency_key: str
    confirmation: Confirmation


def _service(request: Request) -> CatalogBrowseService:
    authorization: AuthorizationPort | None = request.app.state.authorization
    catalog: CatalogBackend | None = request.app.state.registry_mcp_backend
    if authorization is None or catalog is None:
        raise ApiError(
            503,
            "catalog_unavailable",
            "Catalogue indisponible",
            "Le catalogue gouverné n'est pas configuré.",
        )
    return CatalogBrowseService(authorization=authorization, catalog=catalog)


def _detail_service(request: Request) -> CatalogDetailService:
    authorization: AuthorizationPort | None = request.app.state.authorization
    catalog: CatalogBackend | None = request.app.state.registry_mcp_backend
    if authorization is None or catalog is None:
        raise ApiError(
            503,
            "catalog_unavailable",
            "Catalogue indisponible",
            "Le catalogue gouverné n'est pas configuré.",
        )
    return CatalogDetailService(authorization=authorization, catalog=catalog)


def _backend(request: Request) -> CatalogBackend:
    backend: CatalogBackend | None = request.app.state.registry_mcp_backend
    if backend is None:
        raise ApiError(
            503,
            "catalog_unavailable",
            "Catalogue indisponible",
            "Le service de distribution n'est pas configuré.",
        )
    return backend


async def _require_workspace_permission(
    request: Request,
    principal: AuthorizedPrincipal,
    *,
    workspace_id: str,
    relation: str,
) -> None:
    authorization: AuthorizationPort | None = request.app.state.authorization
    if authorization is None:
        raise ApiError(
            503,
            "authorization_unavailable",
            "Autorisation indisponible",
            "Le service d'autorisation n'est pas configuré.",
        )
    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    decision = await authorization.check(
        CheckRequest(
            user=f"user:{principal.principal_id}",
            relation=relation,
            object=f"workspace:{workspace_id}",
            context=context,
            contextual_tuples=contextual_tuples,
        )
    )
    if not decision.allowed:
        raise ApiError(403, "permission_denied", "Accès refusé", "Action non autorisée.")


def _workspace_from_target(target: str) -> str:
    if not target.startswith("workspace:") or not target.removeprefix("workspace:"):
        raise ApiError(
            422,
            "invalid_installation_target",
            "Cible invalide",
            "La cible doit identifier explicitement un espace KYA.",
        )
    return target.removeprefix("workspace:")


def _distribution_error(error: ToolError) -> ApiError:
    code = str(error) or "distribution_failed"
    status = 404 if code.endswith("_not_found") else 409
    return ApiError(
        status,
        code,
        "Opération impossible",
        "La demande ne peut pas être exécutée dans son état actuel.",
    )


@router.get("/artifacts", response_model=CatalogBrowseResponse)
async def browse_catalog(
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    query: Annotated[str, Query(max_length=200)] = "",
    artifact_type: Annotated[list[ArtifactType] | None, Query()] = None,
    owner_workspace_id: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CatalogBrowseResponse:
    """Return only capabilities disclosed by policy in the active unit."""

    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    try:
        items = await _service(request).browse(
            user=f"user:{principal.principal_id}",
            query=CatalogBrowseQuery(
                query=query,
                artifact_types=tuple(artifact_type or ()),
                owner_workspace_id=owner_workspace_id,
                limit=limit,
            ),
            context=context,
            contextual_tuples=contextual_tuples,
        )
    except ValueError as error:
        raise ApiError(
            422,
            "invalid_catalog_query",
            "Recherche invalide",
            str(error),
        ) from error
    return CatalogBrowseResponse(
        items=tuple(
            CatalogSummaryResponse(
                artifact_id=item.public_id,
                artifact_type=item.artifact_type,
                name=item.name,
                summary=item.summary,
                latest_version=item.latest_version,
                lifecycle=item.lifecycle,
                owner_workspace_id=item.owner_workspace_id,
            )
            for item in items
        ),
        active_unit=principal.active_unit_id,
        has_more=len(items) == limit,
    )


@router.get("/artifacts/{artifact_id:path}", response_model=CatalogDetailResponse)
async def get_catalog_artifact(
    artifact_id: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    version: Annotated[str | None, Query(max_length=64)] = None,
) -> CatalogDetailResponse:
    """Return one capability without distinguishing missing from unauthorized."""

    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    detail = await _detail_service(request).get(
        user=f"user:{principal.principal_id}",
        public_id=artifact_id,
        version=version,
        context=context,
        contextual_tuples=contextual_tuples,
    )
    if detail is None:
        raise ApiError(
            404,
            "catalog_artifact_not_found",
            "Capacité introuvable",
            "Cette capacité n'existe pas ou n'est pas accessible dans l'unité active.",
        )
    return CatalogDetailResponse(
        artifact_id=detail.public_id,
        artifact_type=detail.artifact_type,
        name=detail.name,
        summary=detail.summary,
        latest_version=detail.latest_version,
        lifecycle=detail.lifecycle,
        owner_workspace_id=detail.owner_workspace_id,
        versions=detail.versions,
        installable=detail.installable,
        risk=detail.risk,
        source_repository=detail.source_repository,
        content_digest=detail.content_digest,
    )


@router.post(
    "/artifacts/{artifact_id:path}/installation-plan",
    response_model=InstallationPlan,
)
async def request_installation_plan(
    artifact_id: str,
    payload: InstallPlanRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> InstallationPlan:
    """Build a deterministic client-side plan after explicit user consent."""

    workspace_id = _workspace_from_target(payload.target)
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_edit"
    )
    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    detail = await _detail_service(request).get(
        user=f"user:{principal.principal_id}",
        public_id=artifact_id,
        version=payload.version,
        context=context,
        contextual_tuples=contextual_tuples,
    )
    if detail is None:
        raise ApiError(
            404,
            "catalog_artifact_not_found",
            "Capacité introuvable",
            "Cette capacité n'existe pas ou n'est pas accessible dans l'unité active.",
        )
    release_id = await _backend(request).resolve_release_id(artifact_id, payload.version)
    if release_id is None:
        raise ApiError(
            404,
            "catalog_release_not_found",
            "Version introuvable",
            "Cette version n'est pas publiée ou n'est plus disponible.",
        )
    try:
        return await _backend(request).request_install(
            RequestInstallInput(
                release_id=release_id,
                target=payload.target,
                profile=payload.profile,
                scope=payload.scope,
                client_version=payload.client_version,
                idempotency_key=f"plan:{principal.principal_id}:{release_id}",
                confirmation=payload.confirmation,
            )
        )
    except ToolError as error:
        raise _distribution_error(error) from error


@router.post("/installation-receipts", response_model=InstallationRecorded)
async def confirm_installation(
    payload: InstallationReceiptRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> InstallationRecorded:
    """Record a client-verified receipt; the server never writes client files."""

    workspace_id = _workspace_from_target(payload.target)
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_edit"
    )
    try:
        return await _backend(request).confirm_installation(
            ConfirmInstallationInput(
                plan_id=payload.plan_id,
                release_id=payload.release_id,
                target=payload.target,
                profile=payload.profile,
                scope=payload.scope,
                client_version=payload.client_version,
                installed_digest=payload.installed_digest,
                actor_id=principal.principal_id,
                idempotency_key=payload.idempotency_key,
                confirmation=payload.confirmation,
            )
        )
    except ToolError as error:
        raise _distribution_error(error) from error


@router.get("/installations/{installation_id}/updates", response_model=ListUpdatesOutput)
async def list_installation_updates(
    installation_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ListUpdatesOutput:
    backend = _backend(request)
    workspace_id = await backend.resolve_installation_workspace(installation_id)
    if workspace_id is None:
        raise ApiError(
            404,
            "installation_not_found",
            "Installation introuvable",
            "Installation inaccessible.",
        )
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_view"
    )
    return await backend.list_updates(ListUpdatesInput(installation_id=installation_id))


@router.post("/installations/{installation_id}/updates", response_model=OperationAccepted)
async def request_installation_update(
    installation_id: UUID,
    payload: UpdateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> OperationAccepted:
    backend = _backend(request)
    workspace_id = await backend.resolve_installation_workspace(installation_id)
    if workspace_id is None:
        raise ApiError(
            404,
            "installation_not_found",
            "Installation introuvable",
            "Installation inaccessible.",
        )
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_edit"
    )
    try:
        return await backend.request_update(
            RequestUpdateInput(
                installation_id=installation_id,
                release_id=payload.release_id,
                actor_id=principal.principal_id,
                idempotency_key=payload.idempotency_key,
                confirmation=payload.confirmation,
            )
        )
    except ToolError as error:
        raise _distribution_error(error) from error


@router.post("/operations/{operation_id}/update-receipt", response_model=OperationStatus)
async def confirm_installation_update(
    operation_id: UUID,
    payload: UpdateReceiptRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> OperationStatus:
    backend = _backend(request)
    workspace_id = await backend.resolve_operation_workspace(operation_id)
    if workspace_id is None:
        raise ApiError(
            404, "operation_not_found", "Opération introuvable", "Opération inaccessible."
        )
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_edit"
    )
    try:
        return await backend.confirm_update(
            ConfirmUpdateInput(
                operation_id=operation_id,
                installed_digest=payload.installed_digest,
                expected_revision=payload.expected_revision,
                actor_id=principal.principal_id,
                confirmation=payload.confirmation,
            )
        )
    except ToolError as error:
        raise _distribution_error(error) from error


@router.post("/installations/{installation_id}/actions", response_model=OperationStatus)
async def manage_installation(
    installation_id: UUID,
    payload: InstallationActionRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> OperationStatus:
    backend = _backend(request)
    workspace_id = await backend.resolve_installation_workspace(installation_id)
    if workspace_id is None:
        raise ApiError(
            404,
            "installation_not_found",
            "Installation introuvable",
            "Installation inaccessible.",
        )
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_manage"
    )
    try:
        return await backend.manage_installation(
            ManageInstallationInput(
                installation_id=installation_id,
                action=payload.action,
                expected_revision=payload.expected_revision,
                actor_id=principal.principal_id,
                reason=payload.reason,
                idempotency_key=payload.idempotency_key,
                confirmation=payload.confirmation,
            )
        )
    except ToolError as error:
        raise _distribution_error(error) from error


@router.get("/operations/{operation_id}", response_model=OperationStatus)
async def get_distribution_operation(
    operation_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> OperationStatus:
    backend = _backend(request)
    workspace_id = await backend.resolve_operation_workspace(operation_id)
    if workspace_id is None:
        raise ApiError(
            404, "operation_not_found", "Opération introuvable", "Opération inaccessible."
        )
    await _require_workspace_permission(
        request, principal, workspace_id=workspace_id, relation="can_view"
    )
    try:
        return await backend.get_operation(GetOperationInput(operation_id=operation_id))
    except ToolError as error:
        raise _distribution_error(error) from error


__all__ = ["router"]
