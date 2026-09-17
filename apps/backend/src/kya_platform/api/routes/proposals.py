"""Non-developer proposal endpoints: propose, review, and open a governed pull request.

Submitting requires can_propose on the target workspace (broad: any active member). Reviewing,
approving, rejecting and opening the pull request require can_review / can_submit on the
already-known target artifact when one exists, or fall back to can_manage on the target workspace
for a brand-new Skill proposal that has no artifact yet.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.proposal import (
    ProposalNotFoundError,
    ProposalQuotaExceededError,
    ProposalRecord,
    ProposalService,
)
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.contracts.artifact_manifest import ArtifactType as ManifestArtifactType
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType as DomainArtifactType
from kya_platform.domain.catalog import Proposal, ProposalStatus
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

    repository: str | None = Field(default=None, min_length=1, max_length=200)


class ProposalResponse(BaseModel):
    id: UUID
    target_workspace_id: UUID
    slug: str
    artifact_type: str
    artifact_id: UUID | None
    requested_by: UUID
    requested_at: datetime
    status: str
    reviewer_id: UUID | None
    review_reason: str | None
    reviewed_at: datetime | None
    business_owner_id: UUID | None
    technical_owner_id: UUID | None
    pull_request_url: str | None
    merged_commit_sha: str | None


class ProposalSummaryResponse(ProposalResponse):
    file_count: int
    package_size: int


class ProposalListResponse(BaseModel):
    items: list[ProposalSummaryResponse]
    next_cursor: str | None = None


class ProposalFileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    path: str
    kind: str
    size: int
    content_base64: str = Field(alias="contentBase64")


class ProposalEvidenceResponse(BaseModel):
    code: str
    status: Literal["passed", "pending", "failed"]
    summary: str


class ProposalReviewResponse(BaseModel):
    proposal: ProposalResponse
    files: list[ProposalFileResponse]
    evidence: list[ProposalEvidenceResponse]


def _response(proposal: Proposal) -> ProposalResponse:
    return ProposalResponse(
        id=proposal.id,
        target_workspace_id=proposal.target_workspace_id,
        slug=proposal.slug,
        artifact_type=proposal.artifact_type.value,
        artifact_id=proposal.artifact_id,
        requested_by=proposal.requested_by,
        requested_at=proposal.requested_at,
        status=proposal.status.value,
        reviewer_id=proposal.reviewer_id,
        review_reason=proposal.review_reason,
        reviewed_at=proposal.reviewed_at,
        business_owner_id=proposal.business_owner_id,
        technical_owner_id=proposal.technical_owner_id,
        pull_request_url=proposal.pull_request_url,
        merged_commit_sha=proposal.merged_commit_sha,
    )


def _summary(record: ProposalRecord) -> ProposalSummaryResponse:
    package_size = sum(len(item.decoded()) for item in record.package.files)
    return ProposalSummaryResponse(
        **_response(record.proposal).model_dump(),
        file_count=len(record.package.files),
        package_size=package_size,
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
        # The current model defines workspace can_propose as can_view.  Use the
        # stable relation so HTTP and MCP submissions remain compatible while
        # the production authorization model is upgraded independently.
        relation="can_view",
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


@router.get("", response_model=ProposalListResponse)
async def list_proposals(
    target_workspace_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    proposal_status: ProposalStatus | None = None,
    limit: int = 50,
) -> ProposalListResponse:
    if limit < 1 or limit > 100:
        raise ApiError(
            400,
            "invalid_limit",
            "Limite invalide",
            "La limite doit être comprise entre 1 et 100.",
        )
    await _require_permission(
        request,
        principal,
        relation="can_manage",
        object_type="workspace",
        object_id=str(target_workspace_id),
    )
    records = await _service(request).list_for_workspace(
        target_workspace_id,
        status=proposal_status,
        limit=limit,
    )
    return ProposalListResponse(items=[_summary(record) for record in records])


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
    configured_repository: str | None = getattr(request.app.state, "proposal_repository", None)
    if configured_repository is None:
        raise ApiError(
            503,
            "proposal_repository_unavailable",
            "Dépôt de propositions indisponible",
            "Le dépôt GitHub gouverné n'est pas configuré.",
        )
    if payload.repository is not None and payload.repository != configured_repository:
        raise ApiError(
            400,
            "proposal_repository_mismatch",
            "Dépôt non autorisé",
            "La proposition doit être envoyée vers le dépôt configuré par KYA-Platform.",
        )
    try:
        proposal = await _service(request).open_pull_request(
            proposal_id,
            repository=configured_repository,
            correlation_id=_correlation_id(request),
        )
    except (ValueError, ProposalNotFoundError) as error:
        raise _domain_error(error) from error
    return _response(proposal)


@router.get("/{proposal_id}/review", response_model=ProposalReviewResponse)
async def get_proposal_review(
    proposal_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ProposalReviewResponse:
    await _require_review_permission(request, principal, proposal_id)
    record = await _service(request).get_record(proposal_id)
    files = [
        ProposalFileResponse(
            path=item.path,
            kind=item.kind.value,
            size=len(item.decoded()),
            content_base64=item.content_base64,
        )
        for item in record.package.files
    ]
    return ProposalReviewResponse(
        proposal=_response(record.proposal),
        files=files,
        evidence=[
            ProposalEvidenceResponse(
                code="admission_validation",
                status="passed",
                summary="Le paquet satisfait les contrôles d'admission déterministes.",
            ),
            ProposalEvidenceResponse(
                code="file_inventory",
                status="passed",
                summary=(
                    f"{len(files)} fichier(s), "
                    f"{sum(item.size for item in files)} octet(s) vérifiés."
                ),
            ),
            ProposalEvidenceResponse(
                code="human_review",
                status="passed" if record.proposal.reviewed_at is not None else "pending",
                summary=(
                    "La décision humaine est enregistrée."
                    if record.proposal.reviewed_at is not None
                    else "La décision d'un réviseur habilité est requise."
                ),
            ),
        ],
    )


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
