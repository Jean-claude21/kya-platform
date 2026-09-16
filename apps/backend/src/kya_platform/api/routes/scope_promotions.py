"""Scope promotion endpoints: widen an artifact's visibility, never narrow it here.

Submitting requires can_manage on the artifact's current workspace or its owning unit. Review and
approval require can_review / can_approve on the target artifact, mirroring publication.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.scope_promotion import (
    ScopePromotionNotAncestorError,
    ScopePromotionNotFoundError,
    ScopePromotionService,
)
from kya_platform.domain.catalog import ApprovalDecision, ReviewDecision, ScopePromotionRequest
from kya_platform.observability import ApiError

router = APIRouter(prefix="/artifacts/{artifact_id}/scope-promotions", tags=["scope-promotion"])


class CreateScopePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_scope_unit_id: UUID
    target_scope_unit_id: UUID


class ReviewScopePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision


class ApproveScopePromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalDecision


class ScopePromotionResponse(BaseModel):
    id: UUID
    artifact_id: UUID
    current_scope_unit_id: UUID
    target_scope_unit_id: UUID
    status: str


def _response(request: ScopePromotionRequest) -> ScopePromotionResponse:
    return ScopePromotionResponse(
        id=request.id,
        artifact_id=request.artifact_id,
        current_scope_unit_id=request.current_scope_unit_id,
        target_scope_unit_id=request.target_scope_unit_id,
        status=request.status.value,
    )


def _service(request: Request) -> ScopePromotionService:
    service: ScopePromotionService | None = getattr(
        request.app.state, "scope_promotion_service", None
    )
    if service is None:
        raise ApiError(
            503,
            "scope_promotion_service_unavailable",
            "Promotion de portée indisponible",
            "Le service de promotion de portée n'est pas configuré.",
        )
    return service


def _correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def _domain_error(error: Exception) -> ApiError:
    if isinstance(error, ScopePromotionNotFoundError):
        return ApiError(
            404,
            "scope_promotion_not_found",
            "Demande introuvable",
            "Cette demande de promotion de portée n'existe pas.",
        )
    if isinstance(error, ScopePromotionNotAncestorError):
        return ApiError(
            422,
            "scope_promotion_target_not_ancestor",
            "Cible invalide",
            "L'unité cible doit être un ancêtre réel de la portée actuelle.",
        )
    if isinstance(error, PermissionError):
        return ApiError(
            403,
            "scope_promotion_duty_conflict",
            "Responsabilités incompatibles",
            "Cette décision doit être prise par une autre personne habilitée.",
        )
    return ApiError(
        409,
        "scope_promotion_transition_invalid",
        "Transition impossible",
        "L'état actuel de la demande ne permet pas cette opération.",
    )


manage_permission = require_permission(
    relation="can_manage", object_type="artifact", object_parameter="artifact_id"
)


@router.post("", response_model=ScopePromotionResponse, status_code=status.HTTP_201_CREATED)
async def create_scope_promotion(
    artifact_id: UUID,
    payload: CreateScopePromotionRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_permission)],
) -> ScopePromotionResponse:
    try:
        promotion = await _service(request).submit(
            request_id=uuid7(),
            artifact_id=artifact_id,
            current_scope_unit_id=payload.current_scope_unit_id,
            target_scope_unit_id=payload.target_scope_unit_id,
            requested_by=principal.principal_id,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, ScopePromotionNotAncestorError) as error:
        raise _domain_error(error) from error
    return _response(promotion)


review_permission = require_permission(
    relation="can_review", object_type="artifact", object_parameter="artifact_id"
)


@router.post("/{request_id}/reviews", response_model=ScopePromotionResponse)
async def review_scope_promotion(
    artifact_id: UUID,
    request_id: UUID,
    payload: ReviewScopePromotionRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(review_permission)],
) -> ScopePromotionResponse:
    del artifact_id
    try:
        promotion = await _service(request).review(
            request_id,
            actor_id=principal.principal_id,
            decision=payload.decision,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, ScopePromotionNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(promotion)


approve_permission = require_permission(
    relation="can_approve", object_type="artifact", object_parameter="artifact_id"
)


@router.post("/{request_id}/approvals", response_model=ScopePromotionResponse)
async def approve_scope_promotion(
    artifact_id: UUID,
    request_id: UUID,
    payload: ApproveScopePromotionRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(approve_permission)],
) -> ScopePromotionResponse:
    del artifact_id
    try:
        promotion = await _service(request).approve(
            request_id,
            actor_id=principal.principal_id,
            decision=payload.decision,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, ScopePromotionNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(promotion)


@router.post("/{request_id}/apply", response_model=ScopePromotionResponse)
async def apply_scope_promotion(
    artifact_id: UUID,
    request_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(approve_permission)],
) -> ScopePromotionResponse:
    del artifact_id
    try:
        promotion = await _service(request).apply(
            request_id,
            actor_id=principal.principal_id,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, ScopePromotionNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(promotion)


__all__ = ["router"]
