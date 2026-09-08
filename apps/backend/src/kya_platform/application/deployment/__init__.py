"""Provider-neutral deployment contracts and orchestration."""

from dataclasses import dataclass
from typing import Protocol


class DeploymentError(RuntimeError):
    """A provider rejected a deployment operation."""


@dataclass(frozen=True, slots=True)
class DeploymentRequest:
    application: str
    commit_sha: str
    environment: str
    image_digest: str | None = None
    previous_commit_sha: str | None = None

    def __post_init__(self) -> None:
        if not self.application or not self.commit_sha:
            raise ValueError("application and commit_sha are required")
        if self.environment not in {"preview", "staging", "production"}:
            raise ValueError("unsupported deployment environment")


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    id: str
    provider: str
    request: DeploymentRequest
    status: str
    url: str | None = None


class DeploymentProvider(Protocol):
    name: str

    async def deploy(self, request: DeploymentRequest) -> DeploymentRecord: ...

    async def rollback(self, deployment_id: str) -> DeploymentRecord: ...


class PromotionService:
    def __init__(self, providers: dict[str, DeploymentProvider]) -> None:
        self._providers = providers

    async def promote(self, provider: str, request: DeploymentRequest) -> DeploymentRecord:
        adapter = self._providers.get(provider)
        if adapter is None:
            raise ValueError(f"unknown deployment provider: {provider}")
        return await adapter.deploy(request)

    async def rollback(self, provider: str, deployment_id: str) -> DeploymentRecord:
        adapter = self._providers.get(provider)
        if adapter is None:
            raise ValueError(f"unknown deployment provider: {provider}")
        return await adapter.rollback(deployment_id)


__all__ = [
    "DeploymentError",
    "DeploymentProvider",
    "DeploymentRecord",
    "DeploymentRequest",
    "PromotionService",
]
