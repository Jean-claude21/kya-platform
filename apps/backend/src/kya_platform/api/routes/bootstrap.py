"""Authenticated, one-time platform-owner initialization."""

from datetime import UTC, datetime
from typing import Annotated, Protocol, cast
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, SecretStr

from kya_platform.api.security import authenticated_identity
from kya_platform.application.audit import AuditEvent, AuditWriter
from kya_platform.auth import AuthenticatedIdentity, IdentityMappingPort
from kya_platform.bootstrap import (
    BootstrapAlreadyClaimedError,
    BootstrapRejectedError,
    BootstrapService,
    BootstrapUnavailableError,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


class IdentityProvisioner(IdentityMappingPort, Protocol):
    async def provision_identity(
        self, identity: AuthenticatedIdentity, principal_id: UUID
    ) -> UUID: ...


class BootstrapStatusView(BaseModel):
    state: str
    eligible: bool


class BootstrapClaimInput(BaseModel):
    claim_code: SecretStr


class BootstrapClaimView(BaseModel):
    state: str
    principal_id: str
    role: str


def _email(identity: AuthenticatedIdentity) -> str | None:
    email = identity.claims.get("email")
    return email if isinstance(email, str) else None


def _service(request: Request) -> BootstrapService:
    service = cast(BootstrapService | None, request.app.state.bootstrap_service)
    if service is None:
        raise ApiError(
            503,
            "bootstrap_unavailable",
            "Initialisation indisponible",
            "Le parcours d'initialisation sécurisé n'est pas configuré.",
        )
    return service


async def _principal_id(request: Request, identity: AuthenticatedIdentity) -> UUID:
    mapping = cast(IdentityProvisioner | None, request.app.state.identity_mapping)
    if mapping is None:
        raise ApiError(
            503,
            "identity_provisioning_unavailable",
            "Création de profil indisponible",
            "Le stockage des identités n'est pas configuré.",
        )
    principal_id = await mapping.resolve_principal_id(identity)
    return principal_id or await mapping.provision_identity(identity, uuid7())


@router.get("/status", response_model=BootstrapStatusView)
async def bootstrap_status(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(authenticated_identity)],
) -> BootstrapStatusView:
    try:
        state, eligible = await _service(request).status(email=_email(identity))
    except BootstrapUnavailableError as error:
        raise ApiError(
            503,
            "bootstrap_unavailable",
            "Initialisation indisponible",
            "Le parcours d'initialisation sécurisé n'est pas configuré.",
        ) from error
    return BootstrapStatusView(state=state, eligible=eligible)


@router.post("/claim", response_model=BootstrapClaimView)
async def claim_platform_owner(
    payload: BootstrapClaimInput,
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(authenticated_identity)],
) -> BootstrapClaimView:
    principal_id = await _principal_id(request, identity)
    try:
        claim = await _service(request).claim(
            principal_id=principal_id,
            email=_email(identity),
            claim_code=payload.claim_code,
        )
    except BootstrapRejectedError as error:
        raise ApiError(
            403,
            "bootstrap_claim_rejected",
            "Initialisation refusée",
            "L'adresse ou le code d'initialisation ne correspond pas.",
        ) from error
    except BootstrapAlreadyClaimedError as error:
        raise ApiError(
            409,
            "bootstrap_already_claimed",
            "Initialisation déjà terminée",
            "Un propriétaire de la plateforme a déjà été établi.",
        ) from error
    except BootstrapUnavailableError as error:
        raise ApiError(
            503,
            "bootstrap_unavailable",
            "Initialisation indisponible",
            "Le parcours d'initialisation sécurisé n'est pas configuré.",
        ) from error

    audit_writer = cast(AuditWriter | None, request.app.state.audit_writer)
    if audit_writer is not None:
        correlation_id = UUID(cast(str, request.state.correlation_id))
        await audit_writer.append(
            AuditEvent(
                id=uuid7(),
                occurred_at=datetime.now(UTC),
                actor_id=principal_id,
                actor_context={"active_unit_id": "group"},
                action="platform.bootstrap.claim",
                target_type="org_unit",
                target_id="group",
                scope="workspace:platform",
                environment=request.app.state.settings.environment,
                decision="granted",
                outcome="succeeded",
                correlation_id=correlation_id,
                metadata={"role": "platform_owner"},
            )
        )
    return BootstrapClaimView(
        state=claim.state,
        principal_id=str(claim.principal_id),
        role="platform_owner",
    )


__all__ = ["router"]
