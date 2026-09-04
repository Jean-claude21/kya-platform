"""Infisical Universal Auth adapter for machine identities."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import SecretStr


class InfisicalAuthenticationError(RuntimeError):
    """Infisical refused or returned an invalid machine-identity session."""


class InfisicalHttpPort(Protocol):
    async def post_json(self, url: str, payload: Mapping[str, str]) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class MachineAccessToken:
    """Short-lived runtime credential whose representation is always redacted."""

    value: SecretStr
    expires_at: datetime
    max_expires_at: datetime

    def __repr__(self) -> str:
        return (
            "MachineAccessToken(value=SecretStr('**********'), "
            f"expires_at={self.expires_at!r}, max_expires_at={self.max_expires_at!r})"
        )

    def usable_at(self, instant: datetime) -> bool:
        return instant < self.expires_at


@dataclass(frozen=True, slots=True)
class InfisicalMachineIdentityAdapter:
    """Exchange Universal Auth bootstrap credentials for a short-lived access token."""

    http: InfisicalHttpPort
    base_url: str
    client_id: str
    client_secret: SecretStr
    organization_slug: str | None = None
    maximum_token_ttl_seconds: int = 7_200

    def __post_init__(self) -> None:
        normalized = self.base_url.rstrip("/")
        parsed = urlsplit(normalized)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Infisical base URL must be an absolute HTTP URL")
        if parsed.scheme != "https" and not is_local:
            raise ValueError("Infisical requires HTTPS outside local development")
        if not self.client_id.strip() or not self.client_secret.get_secret_value():
            raise ValueError("Infisical machine identity credentials are required")
        if not 1 <= self.maximum_token_ttl_seconds <= 7_200:
            raise ValueError("machine access-token TTL must be between 1 and 7200 seconds")
        object.__setattr__(self, "base_url", normalized)

    async def authenticate(self, *, at: datetime) -> MachineAccessToken:
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret.get_secret_value(),
        }
        if self.organization_slug is not None:
            payload["organizationSlug"] = self.organization_slug
        response = await self.http.post_json(
            f"{self.base_url}/api/v1/auth/universal-auth/login",
            payload,
        )
        try:
            raw_token = response["accessToken"]
            raw_expires_in = response["expiresIn"]
            raw_max_ttl = response["accessTokenMaxTTL"]
        except KeyError as error:
            raise InfisicalAuthenticationError(
                "invalid Infisical authentication response"
            ) from error
        if (
            not isinstance(raw_token, str)
            or not raw_token
            or not isinstance(raw_expires_in, int)
            or isinstance(raw_expires_in, bool)
            or not isinstance(raw_max_ttl, int)
            or isinstance(raw_max_ttl, bool)
            or raw_expires_in <= 0
            or raw_max_ttl <= 0
        ):
            raise InfisicalAuthenticationError("invalid Infisical authentication response")
        effective_ttl = min(raw_expires_in, raw_max_ttl, self.maximum_token_ttl_seconds)
        return MachineAccessToken(
            value=SecretStr(raw_token),
            expires_at=at + timedelta(seconds=effective_ttl),
            max_expires_at=at + timedelta(seconds=min(raw_max_ttl, self.maximum_token_ttl_seconds)),
        )


__all__ = [
    "InfisicalAuthenticationError",
    "InfisicalHttpPort",
    "InfisicalMachineIdentityAdapter",
    "MachineAccessToken",
]
