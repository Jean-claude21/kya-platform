"""Rights-filtered workspace and membership endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from kya_platform.api.security import AuthorizedPrincipal, active_principal, require_permission
from kya_platform.authorization import AuthorizationPort, AuthorizationService, ListObjectsRequest
from kya_platform.authorization.model import active_unit_context
from kya_platform.domain.organization import DateRange
from kya_platform.domain.workspaces import (
    AccessLevel,
    Workspace,
    WorkspaceCommandPort,
    WorkspaceMembership,
    WorkspaceQueryPort,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    name: str
    kind: str
    classification: str


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]


class MembershipRequest(BaseModel):
    principal_id: UUID
    level: AccessLevel
    valid_from: datetime
    valid_until: datetime | None = None
    delegated_by: UUID | None = None


class MembershipResponse(BaseModel):
    workspace_id: UUID
    principal_id: UUID
    level: AccessLevel
    valid_from: datetime
    valid_until: datetime | None


def _workspace_queries(request: Request) -> WorkspaceQueryPort:
    queries: WorkspaceQueryPort | None = getattr(request.app.state, "workspace_queries", None)
    if queries is None:
        raise ApiError(
            503,
            "workspace_service_unavailable",
            "Espaces indisponibles",
            "Le service des espaces n'est pas configuré.",
        )
    return queries


def _workspace_commands(request: Request) -> WorkspaceCommandPort:
    commands: WorkspaceCommandPort | None = getattr(request.app.state, "workspace_commands", None)
    if commands is None:
        raise ApiError(
            503,
            "workspace_service_unavailable",
            "Espaces indisponibles",
            "Le service des espaces n'est pas configuré.",
        )
    return commands


async def _load_workspace(queries: WorkspaceQueryPort, workspace_key: str) -> Workspace:
    workspace = await queries.get(workspace_key)
    if workspace is None:
        raise ApiError(404, "workspace_not_found", "Espace introuvable", "Cet espace n'existe pas.")
    return workspace


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> WorkspaceListResponse:
    authorization: AuthorizationPort | None = request.app.state.authorization
    if authorization is None:
        raise ApiError(
            503,
            "authorization_unavailable",
            "Autorisation indisponible",
            "Le service d'autorisation n'est pas configuré.",
        )
    context, tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    keys = await AuthorizationService(authorization).list_authorized_objects(
        ListObjectsRequest(
            user=f"user:{principal.principal_id}",
            relation="can_view",
            object_type="workspace",
            context=context,
            contextual_tuples=tuples,
        )
    )
    records = await _workspace_queries(request).list_by_keys(keys)
    return WorkspaceListResponse(items=[WorkspaceResponse.model_validate(item) for item in records])


view_workspace = require_permission(
    relation="can_view", object_type="workspace", object_parameter="workspace_key"
)


@router.get("/{workspace_key}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_workspace)],
) -> WorkspaceResponse:
    workspace = await _load_workspace(_workspace_queries(request), workspace_key)
    return WorkspaceResponse.model_validate(workspace)


manage_workspace = require_permission(
    relation="can_manage", object_type="workspace", object_parameter="workspace_key"
)


@router.post(
    "/{workspace_key}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_membership(
    workspace_key: str,
    payload: MembershipRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_workspace)],
) -> MembershipResponse:
    workspace = await _load_workspace(_workspace_queries(request), workspace_key)
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        principal_id=payload.principal_id,
        level=payload.level,
        validity=DateRange(payload.valid_from, payload.valid_until),
        delegated_by=payload.delegated_by,
    )
    created = await _workspace_commands(request).add_membership(
        membership, actor_id=principal.principal_id
    )
    return MembershipResponse(
        workspace_id=created.workspace_id,
        principal_id=created.principal_id,
        level=created.level,
        valid_from=created.validity.valid_from,
        valid_until=created.validity.valid_until,
    )


__all__ = ["router"]
