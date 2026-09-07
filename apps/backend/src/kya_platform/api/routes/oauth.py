"""Authenticated human-consent endpoints for MCP OAuth authorization."""

from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.infrastructure.database.oauth_broker import ConsentRequest
from kya_platform.observability import ApiError

router = APIRouter(prefix="/oauth", tags=["oauth"])


class ConsentBroker(Protocol):
    async def get_consent_request(self, handle: str) -> ConsentRequest | None: ...

    async def approve(
        self, handle: str, *, principal_id: UUID, active_unit_id: str
    ) -> str | None: ...

    async def deny(self, handle: str) -> str | None: ...


class ConsentView(BaseModel):
    client_name: str
    scopes: tuple[str, ...]
    resource: str
    expires_at: datetime


class ConsentDecision(BaseModel):
    redirect_url: str


def _broker(request: Request) -> ConsentBroker:
    broker: ConsentBroker | None = request.app.state.oauth_broker
    if broker is None:
        raise ApiError(
            503,
            "oauth_unavailable",
            "OAuth indisponible",
            "Le courtier OAuth n'est pas actif.",
        )
    return broker


@router.get("/requests/{handle}", response_model=ConsentView)
async def inspect_consent(
    handle: str,
    request: Request,
    _: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ConsentView:
    consent = await _broker(request).get_consent_request(handle)
    if consent is None:
        raise ApiError(
            404,
            "oauth_request_not_found",
            "Demande introuvable",
            "Cette demande est expirée ou déjà traitée.",
        )
    return ConsentView.model_validate(consent, from_attributes=True)


@router.post("/requests/{handle}/approve", response_model=ConsentDecision)
async def approve_consent(
    handle: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ConsentDecision:
    redirect = await _broker(request).approve(
        handle,
        principal_id=principal.principal_id,
        active_unit_id=principal.active_unit_id,
    )
    if redirect is None:
        raise ApiError(
            409,
            "oauth_request_closed",
            "Demande fermée",
            "Cette demande est expirée ou déjà traitée.",
        )
    return ConsentDecision(redirect_url=redirect)


@router.post("/requests/{handle}/deny", response_model=ConsentDecision)
async def deny_consent(
    handle: str,
    request: Request,
    _: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ConsentDecision:
    redirect = await _broker(request).deny(handle)
    if redirect is None:
        raise ApiError(
            409,
            "oauth_request_closed",
            "Demande fermée",
            "Cette demande est expirée ou déjà traitée.",
        )
    return ConsentDecision(redirect_url=redirect)


__all__ = ["router"]
