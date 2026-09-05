"""OpenFGA adapter contract tests."""

from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from kya_platform.authorization import CheckRequest, ContextualTuple, ListObjectsRequest
from kya_platform.infrastructure.openfga import OpenFgaHttpAdapter, OpenFgaUnavailableError


def adapter(handler: httpx.MockTransport) -> tuple[OpenFgaHttpAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return (
        OpenFgaHttpAdapter(
            client,
            api_url="https://fga.example.test",
            api_token=SecretStr("private"),
            store_id="store-1",
            model_id="model-1",
        ),
        client,
    )


@pytest.mark.anyio
async def test_check_pins_model_and_forwards_context() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores/store-1/check"
        assert request.headers["Authorization"] == "Bearer private"
        body = __import__("json").loads(request.content)
        assert body["authorization_model_id"] == "model-1"
        assert body["context"]["current_time"] == "2026-09-05T12:00:00Z"
        assert body["contextual_tuples"]["tuple_keys"][0]["relation"] == "user_in_context"
        return httpx.Response(200, json={"allowed": True})

    policy, client = adapter(httpx.MockTransport(handle))
    async with client:
        decision = await policy.check(
            CheckRequest(
                user="user:1",
                relation="can_view",
                object="workspace:platform",
                context={"current_time": "2026-09-05T12:00:00Z"},
                contextual_tuples=(
                    ContextualTuple(
                        user="user:1",
                        relation="user_in_context",
                        object="org_unit:cvsi",
                    ),
                ),
            )
        )
    assert decision.allowed is True
    assert decision.model_id == "model-1"


@pytest.mark.anyio
async def test_list_objects_returns_only_provider_identifiers() -> None:
    async def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"objects": ["artifact:one", "artifact:two"]})

    policy, client = adapter(httpx.MockTransport(handle))
    async with client:
        objects = await policy.list_objects(
            ListObjectsRequest(user="user:1", relation="can_view", object_type="artifact")
        )
    assert objects == ("artifact:one", "artifact:two")


@pytest.mark.anyio
async def test_platform_owner_grant_writes_pinned_non_pii_tuple() -> None:
    principal_id = UUID("01991fb0-6c00-7000-8000-000000000020")

    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores/store-1/write"
        body = __import__("json").loads(request.content)
        assert body == {
            "authorization_model_id": "model-1",
            "writes": {
                "tuple_keys": [
                    {
                        "user": f"user:{principal_id}",
                        "relation": "base_administrator",
                        "object": "org_unit:group",
                    }
                ]
            },
        }
        return httpx.Response(200, json={})

    policy, client = adapter(httpx.MockTransport(handle))
    async with client:
        await policy.grant_platform_owner(principal_id)


@pytest.mark.anyio
async def test_provider_failures_do_not_leak_response_content() -> None:
    async def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="password=must-not-leak")

    policy, client = adapter(httpx.MockTransport(handle))
    async with client:
        with pytest.raises(OpenFgaUnavailableError) as failure:
            await policy.check(
                CheckRequest(user="user:1", relation="can_view", object="workspace:platform")
            )
    assert "must-not-leak" not in str(failure.value)
