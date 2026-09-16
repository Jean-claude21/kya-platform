import json

import httpx
import pytest
from pydantic import SecretStr

from kya_platform.infrastructure.neon import NeonApiError, NeonPreviewBranchAdapter


@pytest.mark.asyncio
async def test_preview_create_is_idempotent_and_cleanup_is_recoverable() -> None:
    branches: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            search = request.url.params.get("search")
            matching = [branch for branch in branches if branch["name"] == search]
            return httpx.Response(200, json={"branches": matching})
        if request.method == "POST":
            body = json.loads(request.content)
            branch = {"id": "br-preview", "name": body["branch"]["name"]}
            branches.append(branch)
            return httpx.Response(201, json={"branch": branch})
        branches.clear()
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = NeonPreviewBranchAdapter(client, "project", SecretStr("secret"))
        created = await adapter.ensure_preview(42, "a" * 40)
        existing = await adapter.ensure_preview(42, "a" * 40)
        assert created.created is True
        assert existing.created is False
        assert await adapter.cleanup_preview(42) is True
        assert await adapter.cleanup_preview(42) is False


def test_preview_requires_positive_pull_request() -> None:
    with pytest.raises(ValueError):
        NeonPreviewBranchAdapter.branch_name(0)


@pytest.mark.asyncio
async def test_neon_errors_are_redacted() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(401, json={"token": "leak"}))
    ) as client:
        adapter = NeonPreviewBranchAdapter(client, "project", SecretStr("secret"))
        with pytest.raises(NeonApiError) as error:
            await adapter.ensure_preview(1, "a" * 40)
        assert "secret" not in str(error.value)
        assert "leak" not in str(error.value)
