"""Infisical Universal Auth and secret-resolution adapters."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx
from pydantic import SecretStr


class InfisicalAuthenticationError(RuntimeError):
    """Infisical refused or returned an invalid machine-identity session."""


@dataclass(frozen=True, slots=True)
class InfisicalRequestError(RuntimeError):
    """A redacted Infisical request failure safe for logs and API boundaries."""

    status_code: int
    operation: str

    def __str__(self) -> str:
        return f"Infisical {self.operation} failed with status {self.status_code}"


class InfisicalHttpPort(Protocol):
    async def post_json(self, url: str, payload: Mapping[str, str]) -> Mapping[str, object]: ...

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        bearer_token: SecretStr,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class HttpxInfisicalTransport:
    """Perform HTTPS requests without logging credentials or response bodies."""

    client: httpx.AsyncClient

    @staticmethod
    def _mapping(response: httpx.Response, operation: str) -> Mapping[str, object]:
        if response.is_error:
            raise InfisicalRequestError(response.status_code, operation)
        try:
            payload = response.json()
        except ValueError:
            raise InfisicalRequestError(response.status_code, operation) from None
        if not isinstance(payload, dict):
            raise InfisicalRequestError(response.status_code, operation)
        return payload

    async def post_json(self, url: str, payload: Mapping[str, str]) -> Mapping[str, object]:
        response = await self.client.post(url, json=payload)
        return self._mapping(response, "authentication")

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        bearer_token: SecretStr,
    ) -> Mapping[str, object]:
        response = await self.client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {bearer_token.get_secret_value()}"},
        )
        return self._mapping(response, "secret retrieval")


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
class ResolvedSecret:
    """A secret value whose representation is always redacted."""

    key_name: str
    value: SecretStr

    def __repr__(self) -> str:
        return f"ResolvedSecret(key_name={self.key_name!r}, value=SecretStr('**********'))"


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


@dataclass(slots=True)
class InfisicalSecretResolver:
    """Resolve one secret with automatic short-lived token refresh."""

    http: InfisicalHttpPort
    authentication: InfisicalMachineIdentityAdapter
    project_id: str
    environment: str
    secret_path: str = "/"  # noqa: S105 -- path, not credential material
    _token: MachineAccessToken | None = field(default=None, init=False, repr=False)
    _token_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("Infisical project ID is required")
        if self.environment not in {"dev", "staging", "prod"}:
            raise ValueError("Infisical environment is invalid")
        if not self.secret_path.startswith("/"):
            raise ValueError("Infisical secret path must start with /")

    async def _access_token(self, *, at: datetime) -> MachineAccessToken:
        if self._token is not None and self._token.usable_at(at):
            return self._token
        async with self._token_lock:
            if self._token is None or not self._token.usable_at(at):
                self._token = await self.authentication.authenticate(at=at)
            return self._token

    async def resolve(self, key_name: str, *, at: datetime) -> ResolvedSecret:
        if not key_name or "/" in key_name:
            raise ValueError("Infisical secret key name is invalid")
        token = await self._access_token(at=at)
        response = await self.http.get_json(
            f"{self.authentication.base_url}/api/v4/secrets/{quote(key_name, safe='')}",
            params={
                "projectId": self.project_id,
                "environment": self.environment,
                "secretPath": self.secret_path,
                "type": "shared",
                "viewSecretValue": "true",
                "expandSecretReferences": "false",
            },
            bearer_token=token.value,
        )
        secret = response.get("secret")
        if not isinstance(secret, dict):
            raise InfisicalRequestError(502, "secret decoding")
        value = secret.get("secretValue")
        returned_key = secret.get("secretKey")
        if not isinstance(value, str) or returned_key != key_name:
            raise InfisicalRequestError(502, "secret decoding")
        return ResolvedSecret(key_name=key_name, value=SecretStr(value))


__all__ = [
    "HttpxInfisicalTransport",
    "InfisicalAuthenticationError",
    "InfisicalHttpPort",
    "InfisicalMachineIdentityAdapter",
    "InfisicalRequestError",
    "InfisicalSecretResolver",
    "MachineAccessToken",
    "ResolvedSecret",
]
