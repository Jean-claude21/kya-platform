"""Infisical machine identity authentication is short-lived and redacted."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from kya_platform.infrastructure.infisical import (
    InfisicalAuthenticationError,
    InfisicalMachineIdentityAdapter,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


class FakeHttp:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.url = ""
        self.payload: Mapping[str, str] = {}

    async def post_json(self, url: str, payload: Mapping[str, str]) -> Mapping[str, object]:
        self.url = url
        self.payload = payload
        return self.response


@pytest.mark.security
@pytest.mark.asyncio
async def test_universal_auth_returns_capped_redacted_token() -> None:
    http = FakeHttp({"accessToken": "runtime-token", "expiresIn": 7200, "accessTokenMaxTTL": 43200})
    adapter = InfisicalMachineIdentityAdapter(
        http,
        "https://secrets.kya.energy/",
        "machine-client",
        SecretStr("bootstrap-secret"),
        "kya",
        maximum_token_ttl_seconds=900,
    )

    token = await adapter.authenticate(at=NOW)

    assert http.url.endswith("/api/v1/auth/universal-auth/login")
    assert token.expires_at == NOW + timedelta(minutes=15)
    assert token.usable_at(NOW + timedelta(minutes=14))
    assert not token.usable_at(NOW + timedelta(minutes=15))
    assert "runtime-token" not in repr(token)
    assert "bootstrap-secret" not in repr(adapter)


@pytest.mark.security
@pytest.mark.asyncio
async def test_invalid_authentication_response_fails_closed() -> None:
    adapter = InfisicalMachineIdentityAdapter(
        FakeHttp({"message": "unauthorized"}),
        "https://secrets.kya.energy",
        "machine-client",
        SecretStr("bootstrap-secret"),
    )

    with pytest.raises(InfisicalAuthenticationError, match="invalid"):
        await adapter.authenticate(at=NOW)


@pytest.mark.security
def test_infisical_requires_https_outside_local_development() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        InfisicalMachineIdentityAdapter(
            FakeHttp({}),
            "http://secrets.kya.energy",
            "machine-client",
            SecretStr("bootstrap-secret"),
        )
