"""Provider-neutral deployment ports and deterministic adapters."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4


class DeploymentError(RuntimeError):
    """A provider rejected a deployment operation."""


@dataclass(frozen=True, slots=True)
class DeploymentRequest:
    application: str
    commit_sha: str
    environment: str
    image_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.application or not self.commit_sha:
            raise ValueError("application and commit_sha are required")
        if self.environment not in {"preview", "staging", "production"}:
            raise ValueError("unsupported deployment environment")


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    id: UUID
    provider: str
    request: DeploymentRequest
    status: str
    url: str | None = None


class DeploymentProvider(Protocol):
    name: str

    async def deploy(self, request: DeploymentRequest) -> DeploymentRecord: ...

    async def rollback(self, deployment_id: UUID) -> DeploymentRecord: ...


@dataclass(slots=True)
class InMemoryDeploymentProvider:
    """Safe adapter used by tests and local development."""

    name: str
    base_url: str = "http://localhost"
    records: dict[UUID, DeploymentRecord] | None = None

    def __post_init__(self) -> None:
        if self.records is None:
            self.records = {}

    async def deploy(self, request: DeploymentRequest) -> DeploymentRecord:
        record = DeploymentRecord(
            id=uuid4(),
            provider=self.name,
            request=request,
            status="deployed",
            url=f"{self.base_url.rstrip('/')}/{request.application}/{request.environment}",
        )
        assert self.records is not None
        self.records[record.id] = record
        return record

    async def rollback(self, deployment_id: UUID) -> DeploymentRecord:
        assert self.records is not None
        current = self.records.get(deployment_id)
        if current is None:
            raise DeploymentError("deployment not found")
        rolled_back = DeploymentRecord(
            id=current.id,
            provider=current.provider,
            request=current.request,
            status="rolled_back",
            url=current.url,
        )
        self.records[deployment_id] = rolled_back
        return rolled_back


class DokployAdapter(InMemoryDeploymentProvider):
    def __init__(self, base_url: str = "http://dokploy.local") -> None:
        super().__init__(name="dokploy", base_url=base_url)


class CoolifyAdapter(InMemoryDeploymentProvider):
    def __init__(self, base_url: str = "http://coolify.local") -> None:
        super().__init__(name="coolify", base_url=base_url)


__all__ = [
    "CoolifyAdapter",
    "DeploymentError",
    "DeploymentProvider",
    "DeploymentRecord",
    "DeploymentRequest",
    "DokployAdapter",
]
