"""Strict Neon Auth token validation through its provisioned JWKS endpoint."""

from collections.abc import Sequence
from typing import Protocol

import jwt
from anyio import to_thread
from jwt import PyJWK, PyJWKClient

from kya_platform.auth.identity import AuthenticatedIdentity


class InvalidTokenError(ValueError):
    """Raised without leaking why an untrusted token failed validation."""


class SigningKeyResolver(Protocol):
    async def resolve(self, token: str) -> PyJWK:
        """Return the trusted signing key selected from an external JWKS."""


class PyJwkClientResolver:
    """Use PyJWT's bounded, cached JWKS client without blocking the event loop."""

    def __init__(self, jwks_url: str) -> None:
        self._client = PyJWKClient(jwks_url, lifespan=300, timeout=5)

    async def resolve(self, token: str) -> PyJWK:
        return await to_thread.run_sync(self._client.get_signing_key_from_jwt, token)


class NeonJwtVerifier:
    """Verify identity claims only; OpenFGA remains responsible for authorization."""

    _required_claims = ("exp", "iat", "iss", "sub", "aud")

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        signing_keys: SigningKeyResolver,
        algorithms: Sequence[str] = ("RS256", "ES256", "EdDSA"),
        leeway_seconds: int = 30,
    ) -> None:
        if not issuer or not audience or not algorithms:
            raise ValueError("issuer, audience and algorithms are required")
        self._issuer = issuer
        self._audience = audience
        self._signing_keys = signing_keys
        self._algorithms = tuple(algorithms)
        self._leeway_seconds = leeway_seconds

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if not token:
            raise InvalidTokenError("invalid authentication token")

        try:
            signing_key = await self._signing_keys.resolve(token)
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway_seconds,
                options={"require": list(self._required_claims)},
            )
            return AuthenticatedIdentity(
                issuer=str(claims["iss"]),
                subject=str(claims["sub"]),
                claims=claims,
            )
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise InvalidTokenError("invalid authentication token") from error
