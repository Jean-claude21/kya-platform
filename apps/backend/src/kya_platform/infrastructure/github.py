"""GitHub adapter for the proposal pull-request boundary.

The service identity never holds standing merge rights: it authenticates as a GitHub App
installation, opens a branch and a pull request, and requests the reviewer as the required
approver. Merging always remains a human action taken directly on GitHub.
"""

import time
from typing import cast
from uuid import UUID

import httpx
import jwt
from pydantic import SecretStr

from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType

JsonObject = dict[str, object]


class GitHubUnavailableError(RuntimeError):
    """The GitHub adapter could not complete a trustworthy operation."""


def _string_field(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GitHubUnavailableError(f"GitHub response is missing a valid '{key}' field")
    return value


def _nested_object(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise GitHubUnavailableError(f"GitHub response is missing a valid '{key}' object")
    return cast(JsonObject, value)


class GitHubAppPullRequestAdapter:
    """Opens governed pull requests without ever holding standing merge rights."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        app_id: str,
        installation_id: str,
        private_key: SecretStr,
        base_branch: str = "dev",
        api_url: str = "https://api.github.com",
    ) -> None:
        if not app_id or not installation_id or not private_key.get_secret_value():
            raise ValueError("GitHub App credentials are required")
        self._client = client
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key = private_key
        self._base_branch = base_branch
        self._api_url = api_url.rstrip("/")
        self._installation_token: str | None = None
        self._installation_token_expires_at: float = 0.0

    async def open_pull_request(
        self,
        *,
        repository: str,
        slug: str,
        artifact_type: ArtifactType,
        package: ProposalPackage,
        required_approver_id: UUID,
        proposal_id: UUID,
    ) -> str:
        del required_approver_id
        token = await self._installation_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        base_ref = await self._get(
            f"/repos/{repository}/git/ref/heads/{self._base_branch}", headers
        )
        base_sha = _string_field(_nested_object(base_ref, "object"), "sha")
        branch_name = f"feat-proposal-{slug}-{proposal_id.hex[:12]}"
        await self._post(
            f"/repos/{repository}/git/refs",
            headers,
            {"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        base_commit = await self._get(f"/repos/{repository}/git/commits/{base_sha}", headers)
        base_tree_sha = _string_field(_nested_object(base_commit, "tree"), "sha")
        source_directories = {
            ArtifactType.SKILL: "skill",
            ArtifactType.MCP_SERVER: "mcp-server",
            ArtifactType.APPLICATION: "application",
        }
        try:
            source_directory = source_directories[artifact_type]
        except KeyError as error:
            raise ValueError(
                f"unsupported proposal artifact type: {artifact_type.value}"
            ) from error
        prefix = f"catalog/sources/{source_directory}/{slug}"
        tree_entries: list[JsonObject] = []
        for file in package.files:
            blob = await self._post(
                f"/repos/{repository}/git/blobs",
                headers,
                {"content": file.content_base64, "encoding": "base64"},
            )
            tree_entries.append(
                {
                    "path": f"{prefix}/{file.path}",
                    "mode": "100644",
                    "type": "blob",
                    "sha": _string_field(blob, "sha"),
                }
            )
        tree = await self._post(
            f"/repos/{repository}/git/trees",
            headers,
            {"base_tree": base_tree_sha, "tree": tree_entries},
        )
        commit = await self._post(
            f"/repos/{repository}/git/commits",
            headers,
            {
                "message": f"proposal: {slug} ({proposal_id})",
                "tree": _string_field(tree, "sha"),
                "parents": [base_sha],
            },
        )
        commit_sha = _string_field(commit, "sha")
        await self._patch(
            f"/repos/{repository}/git/refs/heads/{branch_name}",
            headers,
            {"sha": commit_sha},
        )
        pull_request = await self._post(
            f"/repos/{repository}/pulls",
            headers,
            {
                "title": f"Proposal: {slug}",
                "head": branch_name,
                "base": self._base_branch,
                "body": (
                    "Automated proposal opened by the KYA Platform service identity. "
                    f"Proposal id: {proposal_id}. Requires review and merge by a human approver."
                ),
            },
        )
        return _string_field(pull_request, "html_url")

    async def get_merge_commit(self, pull_request_url: str) -> str | None:
        token = await self._installation_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        owner_repo, number = self._parse_pull_request_url(pull_request_url)
        pull_request = await self._get(f"/repos/{owner_repo}/pulls/{number}", headers)
        if pull_request.get("merged") is not True:
            return None
        merge_commit_sha = pull_request.get("merge_commit_sha")
        if not isinstance(merge_commit_sha, str) or not merge_commit_sha:
            return None
        return merge_commit_sha

    @staticmethod
    def _parse_pull_request_url(pull_request_url: str) -> tuple[str, str]:
        parts = pull_request_url.rstrip("/").split("/")
        try:
            number = parts[-1]
            repo = parts[-3]
            owner = parts[-4]
        except IndexError as error:
            raise GitHubUnavailableError("malformed pull request url") from error
        return f"{owner}/{repo}", number

    async def _installation_access_token(self) -> str:
        if (
            self._installation_token is not None
            and time.time() < self._installation_token_expires_at
        ):
            return self._installation_token
        now = int(time.time())
        app_jwt = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._private_key.get_secret_value(),
            algorithm="RS256",
        )
        response = await self._client.post(
            f"{self._api_url}/app/installations/{self._installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
        )
        if response.status_code >= 400:
            raise GitHubUnavailableError("could not obtain a GitHub App installation token")
        payload = self._as_object(response)
        self._installation_token = _string_field(payload, "token")
        self._installation_token_expires_at = time.time() + 55 * 60
        return self._installation_token

    async def _get(self, path: str, headers: dict[str, str]) -> JsonObject:
        response = await self._client.get(f"{self._api_url}{path}", headers=headers)
        if response.status_code >= 400:
            raise GitHubUnavailableError(f"GitHub GET {path} failed")
        return self._as_object(response)

    async def _post(self, path: str, headers: dict[str, str], payload: JsonObject) -> JsonObject:
        response = await self._client.post(f"{self._api_url}{path}", headers=headers, json=payload)
        if response.status_code >= 400:
            raise GitHubUnavailableError(f"GitHub POST {path} failed")
        return self._as_object(response)

    async def _patch(self, path: str, headers: dict[str, str], payload: JsonObject) -> JsonObject:
        response = await self._client.patch(f"{self._api_url}{path}", headers=headers, json=payload)
        if response.status_code >= 400:
            raise GitHubUnavailableError(f"GitHub PATCH {path} failed")
        return self._as_object(response)

    @staticmethod
    def _as_object(response: httpx.Response) -> JsonObject:
        decoded = response.json()
        if not isinstance(decoded, dict):
            raise GitHubUnavailableError("GitHub response was not a JSON object")
        return cast(JsonObject, decoded)


__all__ = ["GitHubAppPullRequestAdapter", "GitHubUnavailableError"]
