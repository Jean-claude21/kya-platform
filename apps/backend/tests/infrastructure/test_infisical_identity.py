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
        self.params: Mapping[str, str] = {}
        self.bearer_token = SecretStr("")
        self.get_response: Mapping[str, object] = {}
        self.post_calls = 0

    async def post_json(self, url: str, payload: Mapping[str, str]) -> Mapping[str, object]:
        self.post_calls += 1
        self.url = url
        self.payload = payload
        return self.response

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        bearer_token: SecretStr,
    ) -> Mapping[str, object]:
        self.url = url
        self.params = params
        self.bearer_token = bearer_token
        return self.get_response


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
@pytest.mark.asyncio
async def test_secret_resolver_refreshes_expired_token_and_redacts_value() -> None:
    from kya_platform.infrastructure.infisical import InfisicalSecretResolver

    http = FakeHttp({"accessToken": "runtime-token", "expiresIn": 900, "accessTokenMaxTTL": 900})
    http.get_response = {
        "secret": {"secretKey": "KYA_PLATFORM_T057_PROBE", "secretValue": "preview-ok"}
    }
    authentication = InfisicalMachineIdentityAdapter(
        http,
        "https://app.infisical.com",
        "machine-client",
        SecretStr("bootstrap-secret"),
        maximum_token_ttl_seconds=900,
    )
    resolver = InfisicalSecretResolver(
        http,
        authentication,
        "project-id",
        "staging",
        "/",
    )

    first = await resolver.resolve("KYA_PLATFORM_T057_PROBE", at=NOW)
    second = await resolver.resolve("KYA_PLATFORM_T057_PROBE", at=NOW + timedelta(minutes=15))

    assert first.value.get_secret_value() == "preview-ok"
    assert "preview-ok" not in repr(first)
    assert "runtime-token" not in repr(first)
    assert second.key_name == first.key_name
    assert http.post_calls == 2
    assert http.params["environment"] == "staging"
    assert http.params["secretPath"] == "/"


@pytest.mark.security
@pytest.mark.asyncio
async def test_secret_resolver_rejects_unexpected_payload() -> None:
    from kya_platform.infrastructure.infisical import (
        InfisicalRequestError,
        InfisicalSecretResolver,
    )

    http = FakeHttp({"accessToken": "runtime-token", "expiresIn": 900, "accessTokenMaxTTL": 900})
    http.get_response = {"secret": {"secretKey": "OTHER", "secretValue": "hidden"}}
    resolver = InfisicalSecretResolver(
        http,
        InfisicalMachineIdentityAdapter(
            http,
            "https://app.infisical.com",
            "machine-client",
            SecretStr("bootstrap-secret"),
        ),
        "project-id",
        "staging",
    )

    with pytest.raises(InfisicalRequestError, match="decoding"):
        await resolver.resolve("EXPECTED", at=NOW)


@pytest.mark.security
def test_infisical_requires_https_outside_local_development() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        InfisicalMachineIdentityAdapter(
            FakeHttp({}),
            "http://secrets.kya.energy",
            "machine-client",
            SecretStr("bootstrap-secret"),
        )
