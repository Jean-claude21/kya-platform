"""Secret-reference administration; values never cross this API boundary."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from kya_platform.api.security import AuthorizedPrincipal, active_principal, require_permission
from kya_platform.authorization import AuthorizationPort, AuthorizationService, ListObjectsRequest
from kya_platform.authorization.model import active_unit_context
from kya_platform.observability import ApiError
from kya_platform.secrets import SecretKind, SecretReference, SecretReferencePort, SecretStatus

router = APIRouter(prefix="/secrets", tags=["secrets"])


class SecretReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SecretKind
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    locator: str = Field(min_length=1, max_length=512)
    key_name: str = Field(min_length=1, max_length=128)
    owner_scope: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=255)
    environment: str = Field(pattern=r"^(local|preview|test|production)$")
    expires_at: datetime | None = None


class SecretReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: SecretKind
    provider: str
    locator: str
    key_name: str
    owner_scope: str
    purpose: str
    environment: str
    status: SecretStatus
    created_at: datetime
    rotated_at: datetime | None
    expires_at: datetime | None


class SecretReferenceListResponse(BaseModel):
    items: list[SecretReferenceResponse]


def _references(request: Request) -> SecretReferencePort:
    references: SecretReferencePort | None = getattr(request.app.state, "secret_references", None)
    if references is None:
        raise ApiError(
            503,
            "secret_metadata_unavailable",
            "Références indisponibles",
            "Le registre des références de secrets n'est pas configuré.",
        )
    return references


@router.get("", response_model=SecretReferenceListResponse)
async def list_secret_references(
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> SecretReferenceListResponse:
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
    identifiers = await AuthorizationService(authorization).list_authorized_objects(
        ListObjectsRequest(
            user=f"user:{principal.principal_id}",
            relation="can_view_metadata",
            object_type="secret_reference",
            context=context,
            contextual_tuples=tuples,
        )
    )
    try:
        reference_ids = tuple(UUID(identifier) for identifier in identifiers)
    except ValueError as error:
        raise ApiError(
            502,
            "authorization_response_invalid",
            "Réponse d'autorisation invalide",
            "Une référence autorisée possède un identifiant invalide.",
        ) from error
    records = await _references(request).list_by_ids(reference_ids)
    return SecretReferenceListResponse(
        items=[SecretReferenceResponse.model_validate(record) for record in records]
    )


manage_secret = require_permission(
    relation="can_manage_metadata",
    object_type="secret_reference",
    object_parameter="reference_id",
)


@router.put("/{reference_id}", response_model=SecretReferenceResponse)
async def register_secret_reference(
    reference_id: UUID,
    payload: SecretReferenceRequest,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(manage_secret)],
) -> SecretReferenceResponse:
    reference = SecretReference(
        id=reference_id,
        kind=payload.kind,
        provider=payload.provider,
        locator=payload.locator,
        key_name=payload.key_name,
        owner_scope=payload.owner_scope,
        purpose=payload.purpose,
        environment=payload.environment,
        status=SecretStatus.ACTIVE,
        created_at=datetime.now(UTC),
        expires_at=payload.expires_at,
    )
    await _references(request).register(reference)
    return SecretReferenceResponse.model_validate(reference)


@router.delete("/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_secret_reference(
    reference_id: UUID,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(manage_secret)],
) -> Response:
    await _references(request).revoke(reference_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
