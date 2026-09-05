"""The real HTTP transport fails closed without exposing response bodies."""

import httpx
import pytest
from pydantic import SecretStr

from kya_platform.infrastructure.infisical import (
    HttpxInfisicalTransport,
    InfisicalRequestError,
)


@pytest.mark.security
@pytest.mark.asyncio
async def test_transport_sends_bearer_token_and_returns_mapping() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer runtime-token"
        return httpx.Response(200, json={"secret": {"secretKey": "PROBE"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await HttpxInfisicalTransport(client).get_json(
            "https://app.infisical.com/api/v4/secrets/PROBE",
            params={"projectId": "project"},
            bearer_token=SecretStr("runtime-token"),
        )

    assert result["secret"] == {"secretKey": "PROBE"}


@pytest.mark.security
@pytest.mark.asyncio
async def test_transport_error_is_redacted() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"secretValue": "must-never-leak"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InfisicalRequestError) as denied:
            await HttpxInfisicalTransport(client).get_json(
                "https://app.infisical.com/api/v4/secrets/PROBE",
                params={"projectId": "project"},
                bearer_token=SecretStr("runtime-token"),
            )

    serialized = f"{denied.value!s} {denied.value!r}"
    assert denied.value.status_code == 403
    assert "must-never-leak" not in serialized
    assert "runtime-token" not in serialized


@pytest.mark.security
@pytest.mark.asyncio
async def test_transport_rejects_non_json_response_without_leaking_body() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="secretValue=must-never-leak")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InfisicalRequestError) as invalid:
            await HttpxInfisicalTransport(client).get_json(
                "https://app.infisical.com/api/v4/secrets/PROBE",
                params={"projectId": "project"},
                bearer_token=SecretStr("runtime-token"),
            )

    assert "must-never-leak" not in repr(invalid.value)
