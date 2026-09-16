"""Adapter from verified Neon Auth JWTs to MCP OAuth access tokens."""

from collections.abc import Iterable

from mcp.server.auth.provider import AccessToken

from kya_platform.auth.identity import IdentityMappingPort, TokenVerifier
from kya_platform.auth.neon_jwt import InvalidTokenError


def _scopes(claims: object) -> list[str]:
    if not isinstance(claims, dict):
        return []
    value = claims.get("scope", claims.get("scopes", []))
    if isinstance(value, str):
        return sorted(set(value.split()))
    if isinstance(value, Iterable):
        return sorted({item for item in value if isinstance(item, str) and item})
    return []


class NeonMcpTokenVerifier:
    """Reuse the API's signature and claim validation at the MCP boundary."""

    def __init__(self, verifier: TokenVerifier, identities: IdentityMappingPort) -> None:
        self._verifier = verifier
        self._identities = identities

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            identity = await self._verifier.verify(token)
        except InvalidTokenError:
            return None
        principal_id = await self._identities.resolve_principal_id(identity)
        if principal_id is None:
            return None
        claims = dict(identity.claims)
        client_id = str(claims.get("azp") or claims.get("client_id") or identity.subject)
        expires_at = claims.get("exp")
        authorization_claims: dict[str, object] = {"iss": identity.issuer}
        active_unit = claims.get("active_unit")
        if isinstance(active_unit, str):
            authorization_claims["active_unit"] = active_unit
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=_scopes(claims),
            expires_at=expires_at if isinstance(expires_at, int) else None,
            resource=str(claims.get("aud")) if claims.get("aud") else None,
            subject=str(principal_id),
            claims=authorization_claims,
        )


__all__ = ["NeonMcpTokenVerifier"]
