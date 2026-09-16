import json

import httpx
import pytest
from pydantic import SecretStr

from kya_platform.infrastructure.coolify import CoolifyCloudAdapter
from kya_platform.infrastructure.deployment import DeploymentError, DeploymentRequest


@pytest.mark.asyncio
async def test_coolify_deploy_status_and_rollback() -> None:
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = None
        if request.content:
            payload = json.loads(request.content)
        requests.append((request.method, path, payload))
        if path.endswith("/environments"):
            return httpx.Response(200, json=[{"id": 2, "name": "dev"}])
        if path.endswith("/applications"):
            return httpx.Response(
                200, json=[{"uuid": "app-1", "name": "kya-platform-backend", "environment_id": 2}]
            )
        if path.endswith("/applications/app-1"):
            return httpx.Response(200, json={"uuid": "app-1"})
        if path.endswith("/deploy"):
            return httpx.Response(200, json={"deployments": [{"deployment_uuid": "dep-1"}]})
        if path.endswith("/deployments/dep-1"):
            return httpx.Response(200, json={"status": "finished"})
        if path.endswith("/rollback"):
            return httpx.Response(200, json={"deployment_uuid": "dep-rollback"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = CoolifyCloudAdapter(
            client, "https://app.coolify.io", SecretStr("token"), "project"
        )
        request = DeploymentRequest(
            "kya-platform-backend", "b" * 40, "preview", previous_commit_sha="a" * 40
        )
        deployed = await adapter.deploy(request)
        assert deployed.status == "queued"
        assert ("PATCH", "/api/v1/applications/app-1", {"git_commit_sha": "b" * 40}) in requests
        assert await adapter.status(deployed.id) == "healthy"
        assert (await adapter.rollback(deployed.id)).status == "rolling_back"


@pytest.mark.asyncio
async def test_coolify_error_does_not_disclose_response_or_token() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"token": "provider-secret"})
        )
    ) as client:
        adapter = CoolifyCloudAdapter(
            client, "https://app.coolify.io", SecretStr("token"), "project"
        )
        with pytest.raises(DeploymentError) as error:
            await adapter.deploy(DeploymentRequest("app", "a" * 40, "preview"))
        assert "token" not in str(error.value)
        assert "provider-secret" not in str(error.value)
