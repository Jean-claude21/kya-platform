"""OpenFGA HTTP adapter with pinned model decisions and redacted failures."""

from collections.abc import Mapping
from uuid import UUID

import httpx
from pydantic import SecretStr

from kya_platform.authorization import (
    AuthorizationDecision,
    CheckRequest,
    ContextualTuple,
    ListObjectsRequest,
)


class OpenFgaUnavailableError(RuntimeError):
    """The policy engine could not return a trustworthy decision."""


def _tuple(item: ContextualTuple) -> dict[str, str]:
    return {"user": item.user, "relation": item.relation, "object": item.object}


class OpenFgaHttpAdapter:
    """Evaluate authorization through the OpenFGA HTTP API."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_url: str,
        api_token: SecretStr,
        store_id: str,
        model_id: str,
    ) -> None:
        if not api_url.startswith(("http://", "https://")):
            raise ValueError("OpenFGA API URL must be absolute")
        if not store_id or not model_id or not api_token.get_secret_value():
            raise ValueError("OpenFGA credentials and identifiers are required")
        self._client = client
        self._api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_token.get_secret_value()}"}
        self._store_id = store_id
        self._model_id = model_id

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        payload: dict[str, object] = {
            "authorization_model_id": self._model_id,
            "tuple_key": {
                "user": request.user,
                "relation": request.relation,
                "object": request.object,
            },
            "contextual_tuples": {
                "tuple_keys": [_tuple(item) for item in request.contextual_tuples]
            },
            "context": dict(request.context),
        }
        response = await self._post("check", payload)
        allowed = response.get("allowed")
        if not isinstance(allowed, bool):
            raise OpenFgaUnavailableError("OpenFGA returned an invalid check response")
        return AuthorizationDecision(allowed=allowed, model_id=self._model_id)

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        payload: dict[str, object] = {
            "authorization_model_id": self._model_id,
            "user": request.user,
            "relation": request.relation,
            "type": request.object_type,
            "contextual_tuples": {
                "tuple_keys": [_tuple(item) for item in request.contextual_tuples]
            },
            "context": dict(request.context),
        }
        response = await self._post("list-objects", payload)
        objects = response.get("objects")
        if not isinstance(objects, list) or any(not isinstance(item, str) for item in objects):
            raise OpenFgaUnavailableError("OpenFGA returned an invalid list response")
        return tuple(objects)

    async def grant_platform_owner(self, principal_id: UUID) -> None:
        """Idempotently grant Group administration without storing personal data."""

        await self._post(
            "write",
            {
                "authorization_model_id": self._model_id,
                "writes": {
                    "tuple_keys": [
                        {
                            "user": f"user:{principal_id}",
                            "relation": "base_administrator",
                            "object": "org_unit:group",
                        }
                    ]
                },
            },
        )

    async def grant_artifact_workspace(self, artifact_id: UUID, workspace_id: UUID) -> None:
        """Make a catalog artifact visible through its governed workspace relation."""

        payload = {
            "authorization_model_id": self._model_id,
            "writes": {
                "tuple_keys": [
                    {
                        "user": f"workspace:{workspace_id}",
                        "relation": "workspace",
                        "object": f"artifact:{artifact_id}",
                    }
                ]
            },
        }
        try:
            await self._post("write", payload)
        except OpenFgaUnavailableError:
            decision = await self.check(
                CheckRequest(
                    user=f"workspace:{workspace_id}",
                    relation="workspace",
                    object=f"artifact:{artifact_id}",
                )
            )
            if not decision.allowed:
                raise

    async def _post(self, operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        try:
            response = await self._client.post(
                f"{self._api_url}/stores/{self._store_id}/{operation}",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            decoded = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OpenFgaUnavailableError(f"OpenFGA {operation} failed") from error
        if not isinstance(decoded, dict):
            raise OpenFgaUnavailableError(f"OpenFGA {operation} returned invalid JSON")
        return decoded


__all__ = ["OpenFgaHttpAdapter", "OpenFgaUnavailableError"]
