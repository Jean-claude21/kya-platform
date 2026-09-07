"""Workspace-scoped creation and retrieval of governed artifact drafts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.artifact_registry import (
    ArtifactConflictError,
    ArtifactNotFoundError,
    ArtifactRecord,
    ArtifactRegistryService,
)
from kya_platform.application.artifact_registry.archive import (
    MAX_ARCHIVE_BYTES,
    ArchiveValidationError,
    ArtifactArchiveValidator,
)
from kya_platform.contracts.artifact_package import ArtifactPackage
from kya_platform.observability import ApiError

router = APIRouter(prefix="/workspaces/{workspace_id}/artifacts", tags=["artifacts"])


class CreateArtifactDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    business_owner_id: UUID
    technical_owner_id: UUID
    package: ArtifactPackage


class ArtifactDraftResponse(BaseModel):
    artifact_id: UUID
    version_id: UUID
    workspace_id: UUID
    slug: str
    lifecycle: str
    status: str
    package: ArtifactPackage


def _service(request: Request) -> ArtifactRegistryService:
    service: ArtifactRegistryService | None = getattr(request.app.state, "artifact_registry", None)
    if service is None:
        raise ApiError(
            503,
            "artifact_registry_unavailable",
            "Registre indisponible",
            "Le registre des artefacts n'est pas configuré.",
        )
    return service


def _response(record: ArtifactRecord) -> ArtifactDraftResponse:
    return ArtifactDraftResponse(
        artifact_id=record.artifact_id,
        version_id=record.version_id,
        workspace_id=record.workspace_id,
        slug=record.slug,
        lifecycle=record.lifecycle,
        status=record.status,
        package=record.package,
    )


edit_workspace = require_permission(
    relation="can_edit", object_type="workspace", object_parameter="workspace_id"
)


@router.post("", response_model=ArtifactDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact_draft(
    workspace_id: UUID,
    payload: CreateArtifactDraftRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(edit_workspace)],
) -> ArtifactDraftResponse:
    try:
        record = await _service(request).create_draft(
            workspace_id=workspace_id,
            slug=payload.slug,
            business_owner_id=payload.business_owner_id,
            technical_owner_id=payload.technical_owner_id,
            package=payload.package,
            actor_id=principal.principal_id,
            correlation_id=UUID(request.state.correlation_id),
        )
    except ArtifactConflictError as error:
        raise ApiError(
            409,
            "artifact_conflict",
            "Artefact déjà existant",
            "Cet identifiant ou cette version existe déjà.",
        ) from error
    except ValueError as error:
        raise ApiError(
            422,
            "artifact_identity_invalid",
            "Identité d'artefact incohérente",
            "L'identifiant du manifeste doit correspondre au type et au slug.",
        ) from error
    return _response(record)


@router.post(
    "/imports",
    response_model=ArtifactDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_artifact_archive(
    workspace_id: UUID,
    slug: str,
    business_owner_id: UUID,
    technical_owner_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(edit_workspace)],
) -> ArtifactDraftResponse:
    """Validate a real ZIP package without extraction or execution, then create its draft."""

    content_type = request.headers.get("content-type", "").partition(";")[0].strip().casefold()
    if content_type not in {"application/zip", "application/octet-stream"}:
        raise ApiError(
            415,
            "artifact_archive_media_type_invalid",
            "Format d'archive non pris en charge",
            "Envoyez une archive ZIP avec le type application/zip.",
        )
    archive = bytearray()
    async for chunk in request.stream():
        archive.extend(chunk)
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise ApiError(
                413,
                "artifact_archive_too_large",
                "Archive trop volumineuse",
                "L'archive compressée dépasse la limite autorisée.",
            )
    try:
        validated = ArtifactArchiveValidator().validate(bytes(archive))
        record = await _service(request).create_draft(
            workspace_id=workspace_id,
            slug=slug,
            business_owner_id=business_owner_id,
            technical_owner_id=technical_owner_id,
            package=validated.package,
            actor_id=principal.principal_id,
            correlation_id=UUID(request.state.correlation_id),
        )
    except ArchiveValidationError as error:
        raise ApiError(
            422,
            "artifact_archive_invalid",
            "Paquet d'artefact refusé",
            f"Le paquet ne respecte pas le contrat de sécurité : {error}",
        ) from error
    except ArtifactConflictError as error:
        raise ApiError(
            409,
            "artifact_conflict",
            "Artefact déjà existant",
            "Cet identifiant ou cette version existe déjà.",
        ) from error
    except ValueError as error:
        raise ApiError(
            422,
            "artifact_identity_invalid",
            "Identité d'artefact incohérente",
            "L'identifiant du manifeste doit correspondre au type et au slug.",
        ) from error
    return _response(record)


view_workspace = require_permission(
    relation="can_view", object_type="workspace", object_parameter="workspace_id"
)


@router.get("/{artifact_id}", response_model=ArtifactDraftResponse)
async def get_artifact_draft(
    workspace_id: UUID,
    artifact_id: UUID,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_workspace)],
) -> ArtifactDraftResponse:
    try:
        record = await _service(request).get(artifact_id, workspace_id)
    except ArtifactNotFoundError as error:
        raise ApiError(
            404,
            "artifact_not_found",
            "Artefact introuvable",
            "Cet artefact n'existe pas dans l'espace autorisé.",
        ) from error
    return _response(record)


__all__ = ["router"]
