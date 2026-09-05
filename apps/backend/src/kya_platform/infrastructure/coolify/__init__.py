"""Coolify Cloud implementation of the deployment provider contract."""

from urllib.parse import quote

import httpx
from pydantic import SecretStr

from kya_platform.infrastructure.deployment import (
    DeploymentError,
    DeploymentRecord,
    DeploymentRequest,
)


class CoolifyCloudAdapter:
    name = "coolify"

    def __init__(
        self,
        http: httpx.AsyncClient,
        api_url: str,
        token: SecretStr,
        project_uuid: str,
    ) -> None:
        self._http = http
        self._api_url = f"{api_url.rstrip('/')}/api/v1"
        self._token = token
        self._project_uuid = project_uuid
        self._deployments: dict[str, tuple[str, DeploymentRequest]] = {}

    async def deploy(self, request: DeploymentRequest) -> DeploymentRecord:
        application_uuid = await self._resolve_application(request.application, request.environment)
        payload = await self._request(
            "POST",
            "/deploy",
            operation="queue deployment",
            json={"uuid": application_uuid, "force": False},
        )
        deployments = payload.get("deployments")
        if not isinstance(deployments, list) or not deployments:
            raise DeploymentError("Coolify returned no deployment reference")
        deployment = deployments[0]
        deployment_uuid = (
            deployment.get("deployment_uuid") if isinstance(deployment, dict) else None
        )
        if not isinstance(deployment_uuid, str):
            raise DeploymentError("Coolify returned an invalid deployment reference")
        self._deployments[deployment_uuid] = (application_uuid, request)
        return DeploymentRecord(
            id=deployment_uuid,
            provider=self.name,
            request=request,
            status="queued",
        )

    async def status(self, deployment_id: str) -> str:
        payload = await self._request(
            "GET",
            f"/deployments/{quote(deployment_id)}",
            operation="read deployment status",
        )
        raw = payload.get("status")
        if not isinstance(raw, str):
            raise DeploymentError("Coolify returned an invalid status")
        return self._normalize_status(raw)

    async def rollback(self, deployment_id: str) -> DeploymentRecord:
        known = self._deployments.get(deployment_id)
        if known is None:
            raise DeploymentError("deployment not found in this runtime")
        application_uuid, request = known
        if request.previous_commit_sha is None:
            raise DeploymentError("previous healthy commit is required for rollback")
        payload = await self._request(
            "POST",
            f"/applications/{quote(application_uuid)}/rollback",
            operation="queue rollback",
            json={"commit": request.previous_commit_sha},
        )
        rollback_uuid = payload.get("deployment_uuid")
        if not isinstance(rollback_uuid, str):
            raise DeploymentError("Coolify returned an invalid rollback reference")
        return DeploymentRecord(
            id=rollback_uuid,
            provider=self.name,
            request=request,
            status="rolling_back",
        )

    async def _resolve_application(self, name: str, environment: str) -> str:
        target_environment = "dev" if environment == "preview" else environment
        environments = await self._request(
            "GET",
            f"/projects/{quote(self._project_uuid)}/environments",
            operation="list project environments",
        )
        environment_items = environments.get("items")
        if not isinstance(environment_items, list):
            environment_items = environments.get("data")
        if not isinstance(environment_items, list):
            environment_items = []
        environment_id = next(
            (
                item.get("id")
                for item in environment_items
                if isinstance(item, dict) and item.get("name") == target_environment
            ),
            None,
        )
        applications = await self._request("GET", "/applications", operation="list applications")
        app_items = applications.get("items")
        if not isinstance(app_items, list):
            app_items = applications.get("data")
        if not isinstance(app_items, list):
            app_items = []
        for item in app_items:
            if not isinstance(item, dict) or item.get("name") != name:
                continue
            if environment_id is not None and item.get("environment_id") != environment_id:
                continue
            uuid = item.get("uuid")
            if isinstance(uuid, str):
                return uuid
        raise DeploymentError(
            f"Coolify application is not provisioned: {name}/{target_environment}"
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: dict[str, object] | None = None,
    ) -> dict[str, object]:
        response = await self._http.request(
            method,
            f"{self._api_url}{path}",
            headers={
                "Authorization": f"Bearer {self._token.get_secret_value()}",
                "Accept": "application/json",
            },
            json=json,
        )
        if response.status_code not in {200, 201}:
            raise DeploymentError(f"Coolify {operation} failed with HTTP {response.status_code}")
        payload = response.json()
        if isinstance(payload, list):
            return {"items": payload}
        if not isinstance(payload, dict):
            raise DeploymentError(f"Coolify {operation} returned an invalid response")
        return payload

    @staticmethod
    def _normalize_status(status: str) -> str:
        normalized = status.lower().replace("-", "_")
        if normalized in {"finished", "healthy", "running"}:
            return "healthy"
        if normalized in {"failed", "cancelled", "cancelled_by_user"}:
            return "failed"
        if "progress" in normalized or normalized in {"queued", "pending"}:
            return "deploying"
        return "degraded"


__all__ = ["CoolifyCloudAdapter"]
