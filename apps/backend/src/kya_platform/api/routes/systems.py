"""Rights-filtered registered-system and data-authority endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from kya_platform.api.security import AuthorizedPrincipal, active_principal, require_permission
from kya_platform.authorization import AuthorizationPort, AuthorizationService, ListObjectsRequest
from kya_platform.authorization.model import active_unit_context
from kya_platform.domain.systems import DataAuthority, RegisteredSystem, SystemQueryPort
from kya_platform.observability import ApiError

router = APIRouter(prefix="/systems", tags=["systems"])


class InterfaceResponse(BaseModel):
    name: str
    kind: str
    contract_uri: str
    approved: bool


class SystemResponse(BaseModel):
    key: str
    name: str
    business_owner: str
    technical_owner: str
    status: str
    environments: list[str]
    interfaces: list[InterfaceResponse]
    availability: str


class SystemListResponse(BaseModel):
    items: list[SystemResponse]


class AuthorityResponse(BaseModel):
    category_key: str
    scope: str
    system: SystemResponse
    valid_from: datetime
    valid_until: datetime | None


def _queries(request: Request) -> SystemQueryPort:
    queries: SystemQueryPort | None = getattr(request.app.state, "system_queries", None)
    if queries is None:
        raise ApiError(
            503,
            "system_registry_unavailable",
            "Registre indisponible",
            "Le registre des systèmes n'est pas configuré.",
        )
    return queries


def _response(system: RegisteredSystem) -> SystemResponse:
    return SystemResponse(
        key=system.key,
        name=system.name,
        business_owner=system.business_owner,
        technical_owner=system.technical_owner,
        status=system.status,
        environments=sorted(system.environments),
        interfaces=[
            InterfaceResponse(
                name=item.name,
                kind=item.kind,
                contract_uri=item.contract_uri,
                approved=item.approved,
            )
            for item in system.interfaces
            if item.approved
        ],
        availability=system.availability,
    )


@router.get("", response_model=SystemListResponse)
async def list_systems(
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> SystemListResponse:
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
            object_type="system",
            context=context,
            contextual_tuples=tuples,
        )
    )
    systems = await _queries(request).list_by_keys(keys)
    return SystemListResponse(items=[_response(system) for system in systems])


view_system = require_permission(
    relation="can_view", object_type="system", object_parameter="system_key"
)


@router.get("/{system_key}", response_model=SystemResponse)
async def get_system(
    system_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_system)],
) -> SystemResponse:
    system = await _queries(request).get(system_key)
    if system is None:
        raise ApiError(404, "system_not_found", "Système introuvable", "Ce système n'existe pas.")
    return _response(system)


view_authority = require_permission(
    relation="can_view_authority",
    object_type="data_category",
    object_parameter="category_key",
)


@router.get("/authorities/{category_key}/resolve", response_model=AuthorityResponse)
async def resolve_authority(
    category_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_authority)],
    scope: Annotated[str, Query(min_length=1, max_length=255)],
    at: datetime | None = None,
) -> AuthorityResponse:
    instant = at or datetime.now(UTC)
    resolved = await _queries(request).resolve_authority(category_key, scope, instant)
    if resolved is None:
        raise ApiError(
            404,
            "data_authority_not_found",
            "Autorité introuvable",
            "Aucune source autoritaire n'est déclarée pour ce périmètre.",
        )
    authority, system = resolved
    return _authority_response(authority, system)


def _authority_response(authority: DataAuthority, system: RegisteredSystem) -> AuthorityResponse:
    return AuthorityResponse(
        category_key=authority.category_key,
        scope=authority.scope,
        system=_response(system),
        valid_from=authority.validity.valid_from,
        valid_until=authority.validity.valid_until,
    )


__all__ = ["router"]
