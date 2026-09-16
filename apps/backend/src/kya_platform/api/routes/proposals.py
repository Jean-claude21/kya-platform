"""Non-developer proposal endpoints: propose, review, and open a governed pull request.

Submitting requires can_propose on the target workspace (broad: any active member). Reviewing,
approving, rejecting and opening the pull request require can_review / can_submit on the
already-known target artifact when one exists, or fall back to can_manage on the target workspace
for a brand-new Skill proposal that has no artifact yet.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.proposal import (
    ProposalNotFoundError,
    ProposalQuotaExceededError,
    ProposalService,
)
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.contracts.artifact_manifest import ArtifactType as ManifestArtifactType
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType as DomainArtifactType
from kya_platform.domain.catalog import Proposal
from kya_platform.observability import ApiError

router = APIRouter(prefix="/proposals", tags=["proposals"])


class CreateProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_workspace_id: UUID
    slug: str = Field(min_length=1, max_length=120)
    artifact_type: ManifestArtifactType
    artifact_id: UUID | None = None
    package: ProposalPackage


class ApproveProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_owner_id: UUID
    technical_owner_id: UUID


class RejectProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class OpenPullRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(min_length=1, max_length=200)


class ProposalResponse(BaseModel):
    id: UUID
    target_workspace_id: UUID
    slug: str
    artifact_type: str
    artifact_id: UUID | None
    status: str
    reviewer_id: UUID | None
    review_reason: str | None
    pull_request_url: str | None
    merged_commit_sha: str | None


def _response(proposal: Proposal) -> ProposalResponse:
    return ProposalResponse(
        id=proposal.id,
        target_workspace_id=proposal.target_workspace_id,
        slug=proposal.slug,
        artifact_type=proposal.artifact_type.value,
        artifact_id=proposal.artifact_id,
        status=proposal.status.value,
        reviewer_id=proposal.reviewer_id,
        review_reason=proposal.review_reason,
        pull_request_url=proposal.pull_request_url,
        merged_commit_sha=proposal.merged_commit_sha,
    )


def _service(request: Request) -> ProposalService:
    service: ProposalService | None = getattr(request.app.state, "proposal_service", None)
    if service is None:
        raise ApiError(
            503,
            "proposal_service_unavailable",
            "Propositions indisponibles",
            "Le service de propositions n'est pas configuré.",
        )
    return service


def _correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def _domain_error(error: Exception) -> ApiError:
    if isinstance(error, ProposalNotFoundError):
        return ApiError(
            404,
            "proposal_not_found",
            "Proposition introuvable",
            "Cette proposition n'existe pas ou n'est pas accessible.",
        )
    if isinstance(error, ProposalQuotaExceededError):
        return ApiError(
            429,
            "proposal_quota_exceeded",
            "Trop de propositions en attente",
            str(error),
        )
    if isinstance(error, PermissionError):
        return ApiError(
            403,
            "proposal_duty_conflict",
            "Responsabilités incompatibles",
            "Cette décision doit être prise par une autre personne habilitée.",
        )
    return ApiError(
        409,
        "proposal_transition_invalid",
        "Transition impossible",
        "L'état actuel de la proposition ne permet pas cette opération.",
    )


async def _require_permission(
    request: Request,
    principal: AuthorizedPrincipal,
    *,
    relation: str,
    object_type: str,
    object_id: str,
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
            object=f"{object_type}:{object_id}",
            context=context,
            contextual_tuples=contextual_tuples,
        )
    )
    if not decision.allowed:
        raise ApiError(403, "permission_denied", "Accès refusé", "Action non autorisée.")


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    payload: CreateProposalRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    await _require_permission(
        request,
        principal,
        relation="can_propose",
        object_type="workspace",
        object_id=str(payload.target_workspace_id),
    )
    try:
        proposal = await _service(request).submit(
            proposal_id=uuid7(),
            target_workspace_id=payload.target_workspace_id,
            slug=payload.slug,
            artifact_type=DomainArtifactType(payload.artifact_type.value),
            artifact_id=payload.artifact_id,
            package=payload.package,
            requested_by=principal.principal_id,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, ProposalQuotaExceededError) as error:
        raise _domain_error(error) from error
    return _response(proposal)


async def _require_review_permission(
    request: Request, principal: AuthorizedPrincipal, proposal_id: UUID
) -> Proposal:
    try:
        proposal = await _service(request).get(proposal_id)
    except ProposalNotFoundError as error:
        raise _domain_error(error) from error
    if proposal.artifact_id is not None:
        await _require_permission(
            request,
            principal,
            relation="can_review",
            object_type="artifact",
            object_id=str(proposal.artifact_id),
        )
    else:
        await _require_permission(
            request,
            principal,
            relation="can_manage",
            object_type="workspace",
            object_id=str(proposal.target_workspace_id),
        )
    return proposal


@router.post("/{proposal_id}/approvals", response_model=ProposalResponse)
async def approve_proposal(
    proposal_id: UUID,
    payload: ApproveProposalRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    await _require_review_permission(request, principal, proposal_id)
    try:
        proposal = await _service(request).approve(
            proposal_id,
            reviewer_id=principal.principal_id,
            business_owner_id=payload.business_owner_id,
            technical_owner_id=payload.technical_owner_id,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, ProposalNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(proposal)


@router.post("/{proposal_id}/rejections", response_model=ProposalResponse)
async def reject_proposal(
    proposal_id: UUID,
    payload: RejectProposalRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    await _require_review_permission(request, principal, proposal_id)
    try:
        proposal = await _service(request).reject(
            proposal_id,
            reviewer_id=principal.principal_id,
            reason=payload.reason,
            at=datetime.now(UTC),
            correlation_id=_correlation_id(request),
        )
    except (ValueError, PermissionError, ProposalNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(proposal)


@router.post("/{proposal_id}/pull-request", response_model=ProposalResponse)
async def open_proposal_pull_request(
    proposal_id: UUID,
    payload: OpenPullRequestRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    await _require_review_permission(request, principal, proposal_id)
    try:
        proposal = await _service(request).open_pull_request(
            proposal_id,
            repository=payload.repository,
            correlation_id=_correlation_id(request),
        )
    except (ValueError, ProposalNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(proposal)


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal_status(
    proposal_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    proposal = await _require_review_permission(request, principal, proposal_id)
    return _response(proposal)


@router.post("/{proposal_id}/merge-status", response_model=ProposalResponse)
async def poll_proposal_merge_status(
    proposal_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalResponse:
    """Check a linked pull request; never trusts a merge commit from client input."""

    await _require_review_permission(request, principal, proposal_id)
    try:
        proposal = await _service(request).poll_merge_status(
            proposal_id, correlation_id=_correlation_id(request)
        )
    except ProposalNotFoundError as error:
        raise _domain_error(error) from error
    return _response(proposal)


__all__ = ["router"]
