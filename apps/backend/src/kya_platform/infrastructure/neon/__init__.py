"""Neon branch automation for isolated pull-request previews."""

from dataclasses import dataclass
from urllib.parse import quote

import httpx
from pydantic import SecretStr


class NeonApiError(RuntimeError):
    """A redacted Neon API failure."""

    def __init__(self, operation: str, status_code: int) -> None:
        self.operation = operation
        self.status_code = status_code
        super().__init__(f"Neon {operation} failed with HTTP {status_code}")


@dataclass(frozen=True, slots=True)
class NeonPreviewBranch:
    id: str
    name: str
    created: bool


class NeonPreviewBranchAdapter:
    """Idempotently create and clean up recoverable Neon preview branches."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        project_id: str,
        api_key: SecretStr,
        base_url: str = "https://console.neon.tech/api/v2",
    ) -> None:
        self._http = http
        self._project_id = project_id
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @staticmethod
    def branch_name(pull_request: int) -> str:
        if pull_request < 1:
            raise ValueError("pull request number must be positive")
        return f"preview/pr-{pull_request}"

    async def ensure_preview(self, pull_request: int, commit_sha: str) -> NeonPreviewBranch:
        name = self.branch_name(pull_request)
        current = await self._find(name)
        if current is not None:
            branch_id = current.get("id")
            if not isinstance(branch_id, str):
                raise NeonApiError("decode preview branch", 502)
            return NeonPreviewBranch(id=branch_id, name=name, created=False)
        response = await self._request(
            "POST",
            f"/projects/{quote(self._project_id)}/branches",
            operation="create preview branch",
            json={
                "branch": {
                    "name": name,
                    "protected": False,
                    "annotation_value": {
                        "kya.pull_request": str(pull_request),
                        "kya.commit": commit_sha,
                    },
                }
            },
        )
        branch = response.get("branch")
        if not isinstance(branch, dict) or not isinstance(branch.get("id"), str):
            raise NeonApiError("decode preview branch", 502)
        return NeonPreviewBranch(id=branch["id"], name=name, created=True)

    async def cleanup_preview(self, pull_request: int) -> bool:
        current = await self._find(self.branch_name(pull_request))
        if current is None:
            return False
        branch_id = current.get("id")
        if not isinstance(branch_id, str):
            raise NeonApiError("decode preview branch", 502)
        await self._request(
            "DELETE",
            f"/projects/{quote(self._project_id)}/branches/{quote(branch_id)}",
            operation="delete preview branch",
        )
        return True

    async def _find(self, name: str) -> dict[str, object] | None:
        payload = await self._request(
            "GET",
            f"/projects/{quote(self._project_id)}/branches",
            operation="list preview branches",
            params={"search": name, "limit": "100"},
        )
        branches = payload.get("branches")
        if not isinstance(branches, list):
            raise NeonApiError("decode branch list", 502)
        return next(
            (
                branch
                for branch in branches
                if isinstance(branch, dict) and branch.get("name") == name
            ),
            None,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        response = await self._http.request(
            method,
            f"{self._base_url}{path}",
            headers={
                "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                "Accept": "application/json",
            },
            json=json,
            params=params,
        )
        if response.status_code not in {200, 201, 204}:
            raise NeonApiError(operation, response.status_code)
        if response.status_code == 204 or not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise NeonApiError(f"decode {operation}", 502)
        return payload


__all__ = ["NeonApiError", "NeonPreviewBranch", "NeonPreviewBranchAdapter"]
