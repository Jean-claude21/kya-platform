"""Governed submission, review, approval and release endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.publication import PublicationNotFoundError, PublicationService
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    ReviewDecision,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/artifacts/{artifact_id}/publication-requests", tags=["publication"])


class CandidateRequest(BaseModel):
    version: str
    commit_sha: str = Field(min_length=40, max_length=40)
    content_digest: str = Field(min_length=64, max_length=64)
    manifest_digest: str = Field(min_length=64, max_length=64)


class ReviewRequest(BaseModel):
    decision: ReviewDecision


class ApprovalRequest(BaseModel):
    decision: ApprovalDecision


class PublishRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)


class PublicationResponse(BaseModel):
    id: UUID
    artifact_id: UUID
    version: str
    content_digest: str
    status: str


def _service(request: Request) -> PublicationService:
    service: PublicationService | None = getattr(request.app.state, "publication_service", None)
    if service is None:
        raise ApiError(
            503,
            "publication_service_unavailable",
            "Publication indisponible",
            "Le service de publication n'est pas configuré.",
        )
    return service


def _correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def _response(publication: PublicationRequest) -> PublicationResponse:
    return PublicationResponse(
        id=publication.id,
        artifact_id=publication.candidate.artifact_id,
        version=publication.candidate.version,
        content_digest=publication.candidate.content_digest,
        status=publication.status.value,
    )


def _domain_error(error: Exception) -> ApiError:
    if isinstance(error, PublicationNotFoundError):
        return ApiError(
            404,
            "publication_request_not_found",
            "Demande introuvable",
            "Cette demande de publication n'existe pas.",
        )
    if isinstance(error, PermissionError):
        return ApiError(
            403,
            "publication_duty_conflict",
            "Responsabilités incompatibles",
            "Cette décision doit être prise par une autre personne habilitée.",
        )
    return ApiError(
        409,
        "publication_transition_invalid",
        "Transition impossible",
        "L'état actuel ou la version candidate ne permet pas cette opération.",
    )


submit_permission = require_permission(
    relation="can_submit", object_type="artifact", object_parameter="artifact_id"
)


@router.post("", response_model=PublicationResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_publication(
    artifact_id: UUID,
    payload: CandidateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(submit_permission)],
) -> PublicationResponse:
    try:
        publication = await _service(request).submit(
            request_id=uuid7(),
            candidate=ArtifactVersion(
                artifact_id,
                payload.version,
                payload.commit_sha,
                payload.content_digest,
                payload.manifest_digest,
            ),
            actor_id=principal.principal_id,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
            separation_of_duties=True,
        )
    except (ValueError, PermissionError, PublicationNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(publication)


review_permission = require_permission(
    relation="can_review", object_type="artifact", object_parameter="artifact_id"
)


@router.post("/{request_id}/reviews", response_model=PublicationResponse)
async def review_publication(
    artifact_id: UUID,
    request_id: UUID,
    payload: ReviewRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(review_permission)],
) -> PublicationResponse:
    del artifact_id
    try:
        publication = await _service(request).review(
            request_id,
            actor_id=principal.principal_id,
            decision=payload.decision,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, PublicationNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(publication)


approve_permission = require_permission(
    relation="can_approve", object_type="artifact", object_parameter="artifact_id"
)


@router.post("/{request_id}/approvals", response_model=PublicationResponse)
async def approve_publication(
    artifact_id: UUID,
    request_id: UUID,
    payload: ApprovalRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(approve_permission)],
) -> PublicationResponse:
    del artifact_id
    try:
        publication = await _service(request).approve(
            request_id,
            actor_id=principal.principal_id,
            decision=payload.decision,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, PublicationNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(publication)


@router.post("/{request_id}/publish", response_model=PublicationResponse)
async def publish_artifact(
    artifact_id: UUID,
    request_id: UUID,
    payload: PublishRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(approve_permission)],
) -> PublicationResponse:
    del artifact_id
    try:
        publication = await _service(request).publish(
            request_id,
            actor_id=principal.principal_id,
            content_digest=payload.content_digest,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, PublicationNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(publication)


__all__ = ["router"]
