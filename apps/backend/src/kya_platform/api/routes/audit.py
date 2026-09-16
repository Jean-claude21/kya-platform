"""Scoped auditor API with an independent protected-content mandate."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.audit import AuditQuery, AuditQueryService
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.observability import ApiError

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    actor_context: dict[str, Any]
    action: str
    target_type: str
    target_id: str
    scope: str
    environment: str | None
    decision: str | None
    outcome: str
    correlation_id: UUID
    causation_id: UUID | None
    metadata: dict[str, Any]
    protected_content: dict[str, Any] | None


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    content_mode: str


def _service(request: Request) -> AuditQueryService:
    service: AuditQueryService | None = getattr(request.app.state, "audit_queries", None)
    if service is None:
        raise ApiError(
            503,
            "audit_service_unavailable",
            "Audit indisponible",
            "Le service de consultation d'audit n'est pas configuré.",
        )
    return service


async def _is_allowed(
    request: Request,
    principal: AuthorizedPrincipal,
    *,
    relation: str,
    workspace_key: str,
) -> bool:
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
    decision = await authorization.check(
        CheckRequest(
            user=f"user:{principal.principal_id}",
            relation=relation,
            object=f"workspace:{workspace_key}",
            context=context,
            contextual_tuples=tuples,
        )
    )
    return decision.allowed


@router.get("/workspaces/{workspace_key}/events", response_model=AuditEventListResponse)
async def list_audit_events(
    workspace_key: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    target_type: Annotated[str | None, Query(max_length=120)] = None,
    target_id: Annotated[str | None, Query(max_length=255)] = None,
    correlation_id: UUID | None = None,
    include_protected_content: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AuditEventListResponse:
    """List one workspace timeline after filtering access, not after disclosure."""

    if not await _is_allowed(request, principal, relation="can_audit", workspace_key=workspace_key):
        raise ApiError(
            403,
            "permission_denied",
            "Accès refusé",
            "Vous ne disposez pas du mandat d'audit requis.",
        )

    may_view_content = False
    if include_protected_content:
        may_view_content = await _is_allowed(
            request,
            principal,
            relation="can_view_audit_content",
            workspace_key=workspace_key,
        )
        if not may_view_content:
            raise ApiError(
                403,
                "audit_content_permission_denied",
                "Contenu protégé",
                "Le mandat d'audit ne permet pas de consulter le contenu métier.",
            )

    views = await _service(request).list_events(
        AuditQuery(
            scope=f"workspace:{workspace_key}",
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
            limit=limit,
        ),
        may_view_protected_content=may_view_content,
    )
    return AuditEventListResponse(
        content_mode="protected" if may_view_content else "metadata_only",
        items=[
            AuditEventResponse(
                id=view.event.id,
                occurred_at=view.event.occurred_at,
                actor_id=view.event.actor_id,
                actor_context=dict(view.event.actor_context),
                action=view.event.action,
                target_type=view.event.target_type,
                target_id=view.event.target_id,
                scope=view.event.scope,
                environment=view.event.environment,
                decision=view.event.decision,
                outcome=view.event.outcome,
                correlation_id=view.event.correlation_id,
                causation_id=view.event.causation_id,
                metadata=dict(view.event.metadata),
                protected_content=(
                    dict(view.protected_content) if view.protected_content is not None else None
                ),
            )
            for view in views
        ],
    )


__all__ = ["router"]
