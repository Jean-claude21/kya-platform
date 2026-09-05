"""Authenticated account bootstrap and MCP readiness."""

from typing import Annotated, Protocol, cast
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kya_platform.api.security import authenticated_identity
from kya_platform.auth import AuthenticatedIdentity, IdentityMappingPort
from kya_platform.observability import ApiError

router = APIRouter(prefix="/account", tags=["account"])


class AccountView(BaseModel):
    principal_id: str
    email: str | None
    active_unit_id: str
    mcp_ready: bool


class IdentityProvisioner(IdentityMappingPort, Protocol):
    async def provision_identity(
        self, identity: AuthenticatedIdentity, principal_id: UUID
    ) -> UUID: ...


@router.get("/me", response_model=AccountView)
async def account_me(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(authenticated_identity)],
) -> AccountView:
    """Provision the first internal identity binding and return safe session metadata."""

    mapping = cast(IdentityProvisioner | None, request.app.state.identity_mapping)
    if mapping is None:
        raise ApiError(
            503,
            "identity_provisioning_unavailable",
            "Création de profil indisponible",
            "Le stockage des identités n'est pas configuré.",
        )
    principal_id = await mapping.resolve_principal_id(identity)
    if principal_id is None:
        principal_id = await mapping.provision_identity(identity, uuid7())
    active_unit_id = request.headers.get("X-KYA-Unit-ID", "group")
    email = identity.claims.get("email")
    return AccountView(
        principal_id=str(principal_id),
        email=email if isinstance(email, str) else None,
        active_unit_id=active_unit_id,
        mcp_ready=True,
    )


__all__ = ["router"]
