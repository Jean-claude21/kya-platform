"""Governed submission, review, approval and release endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.publication import PublicationNotFoundError, PublicationService
from kya_platform.application.publication.evidence import (
    AttestationKind,
    AttestationRecord,
    AttestationRepository,
)
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    ReviewDecision,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/artifacts/{artifact_id}/publication-requests", tags=["publication"])
attestation_router = APIRouter(
    prefix="/artifacts/{artifact_id}/versions/{version_id}/attestations",
    tags=["publication"],
)


class CandidateRequest(BaseModel):
    version: str
    commit_sha: str = Field(min_length=40, max_length=40)
    content_digest: str = Field(min_length=64, max_length=64)
    manifest_digest: str = Field(min_length=64, max_length=64)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)


class AttestationRequest(BaseModel):
    kind: AttestationKind
    result: Literal["passed", "failed"]
    evidence_uri: HttpUrl
    valid_until: datetime | None = None

    @field_validator("valid_until")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("attestation expiration must be timezone-aware")
        return value


class AttestationResponse(BaseModel):
    id: UUID
    artifact_version_id: UUID
    kind: AttestationKind
    issuer_id: UUID
    subject_digest: str
    result: str
    valid_from: datetime
    valid_until: datetime | None
    evidence_uri: str


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


def _attestations(request: Request) -> AttestationRepository:
    repository: AttestationRepository | None = getattr(
        request.app.state, "attestation_repository", None
    )
    if repository is None:
        raise ApiError(
            503,
            "attestation_service_unavailable",
            "Attestations indisponibles",
            "Le service de preuves de publication n'est pas configuré.",
        )
    return repository


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
            evidence_ids=payload.evidence_ids,
        )
    except (ValueError, PermissionError, PublicationNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(publication)


attest_permission = require_permission(
    relation="can_review", object_type="artifact", object_parameter="artifact_id"
)


@attestation_router.post(
    "", response_model=AttestationResponse, status_code=status.HTTP_201_CREATED
)
async def create_attestation(
    artifact_id: UUID,
    version_id: UUID,
    payload: AttestationRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(attest_permission)],
) -> AttestationResponse:
    try:
        record: AttestationRecord = await _attestations(request).create(
            artifact_id=artifact_id,
            version_id=version_id,
            kind=payload.kind,
            issuer_id=principal.principal_id,
            result=payload.result,
            valid_from=datetime.now(UTC),
            valid_until=payload.valid_until,
            evidence_uri=str(payload.evidence_uri),
            correlation_id=_correlation_id(request),
        )
    except ValueError as error:
        raise ApiError(
            422,
            "attestation_invalid",
            "Preuve de publication invalide",
            str(error),
        ) from error
    return AttestationResponse(
        id=record.id,
        artifact_version_id=record.artifact_version_id,
        kind=record.kind,
        issuer_id=record.issuer_id,
        subject_digest=record.subject_digest,
        result=record.result,
        valid_from=record.valid_from,
        valid_until=record.valid_until,
        evidence_uri=record.evidence_uri,
    )


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


__all__ = ["attestation_router", "router"]
