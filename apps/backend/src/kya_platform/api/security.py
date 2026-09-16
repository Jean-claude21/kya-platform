"""FastAPI authentication and authorization dependency guards."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.datastructures import State

from kya_platform.auth import (
    AuthenticatedIdentity,
    IdentityMappingPort,
    InvalidTokenError,
    NeonJwtVerifier,
    PyJwkClientResolver,
    TokenVerifier,
)
from kya_platform.authorization import (
    AuthorizationPort,
    CheckRequest,
    active_unit_context,
)
from kya_platform.config import Settings
from kya_platform.observability import ApiError

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthorizedPrincipal:
    principal_id: UUID
    identity: AuthenticatedIdentity
    active_unit_id: str


async def active_principal(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(authenticated_identity)],
) -> AuthorizedPrincipal:
    """Resolve the internal principal and require an explicit organization context."""

    mapping: IdentityMappingPort | None = request.app.state.identity_mapping
    if mapping is None:
        raise ApiError(
            503,
            "authorization_unavailable",
            "Autorisation indisponible",
            "Le service d'autorisation n'est pas configuré.",
        )
    principal_id = await mapping.resolve_principal_id(identity)
    if principal_id is None:
        raise ApiError(
            403,
            "identity_not_linked",
            "Identité non rattachée",
            "Cette identité n'est pas rattachée à un principal KYA actif.",
        )
    active_unit_id = request.headers.get("X-KYA-Unit-ID")
    if not active_unit_id:
        raise ApiError(
            400,
            "active_unit_required",
            "Unité active requise",
            "Sélectionnez explicitement l'unité organisationnelle active.",
        )
    return AuthorizedPrincipal(principal_id, identity, active_unit_id)


def configure_security_runtime(app_state: State, settings: Settings) -> None:
    """Configure token validation now; infrastructure adapters arrive during startup."""

    issuer = settings.neon_auth_issuer
    jwks_url = settings.neon_auth_jwks_url
    if (issuer is None) != (jwks_url is None):
        raise RuntimeError("Neon Auth issuer and JWKS URL must be configured together")

    verifier: TokenVerifier | None = None
    if issuer is not None and jwks_url is not None:
        verifier = NeonJwtVerifier(
            issuer=issuer,
            audience=settings.neon_auth_audience,
            signing_keys=PyJwkClientResolver(jwks_url),
        )

    app_state.token_verifier = verifier
    app_state.identity_mapping = None
    app_state.authorization = None


async def authenticated_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthenticatedIdentity:
    """Validate the Bearer token through Neon Auth's JWKS contract."""

    if credentials is None:
        raise ApiError(
            401,
            "authentication_required",
            "Authentification requise",
            "Un jeton Bearer valide est requis.",
            {"WWW-Authenticate": "Bearer"},
        )
    verifier: TokenVerifier | None = request.app.state.token_verifier
    if verifier is None:
        raise ApiError(
            503,
            "authentication_unavailable",
            "Authentification indisponible",
            "Le service d'authentification n'est pas configuré.",
        )
    try:
        return await verifier.verify(credentials.credentials)
    except InvalidTokenError as error:
        raise ApiError(
            401,
            "invalid_authentication_token",
            "Jeton invalide",
            "Le jeton d'authentification est invalide ou expiré.",
            {"WWW-Authenticate": "Bearer"},
        ) from error


def require_permission(
    *, relation: str, object_type: str, object_parameter: str
) -> Callable[..., Awaitable[AuthorizedPrincipal]]:
    """Build a guard that resolves identity, active unit and OpenFGA permission."""

    async def dependency(
        request: Request,
        principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    ) -> AuthorizedPrincipal:
        authorization: AuthorizationPort | None = request.app.state.authorization
        if authorization is None:
            raise ApiError(
                503,
                "authorization_unavailable",
                "Autorisation indisponible",
                "Le service d'autorisation n'est pas configuré.",
            )

        object_id = request.path_params.get(object_parameter)
        if not isinstance(object_id, str) or not object_id:
            raise RuntimeError(f"missing guarded path parameter: {object_parameter}")

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
            raise ApiError(
                403,
                "permission_denied",
                "Accès refusé",
                "Vous ne disposez pas de l'autorisation requise.",
            )

        return principal

    return dependency


__all__ = [
    "AuthorizedPrincipal",
    "active_principal",
    "authenticated_identity",
    "configure_security_runtime",
    "require_permission",
]
