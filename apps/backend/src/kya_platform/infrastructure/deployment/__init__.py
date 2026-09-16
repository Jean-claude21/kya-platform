"""Deterministic deployment adapters used by tests and local development."""

from dataclasses import dataclass
from uuid import uuid4

from kya_platform.application.deployment import (
    DeploymentError,
    DeploymentProvider,
    DeploymentRecord,
    DeploymentRequest,
)


@dataclass(slots=True)
class InMemoryDeploymentProvider:
    """Safe adapter used by tests and local development."""

    name: str
    base_url: str = "http://localhost"
    records: dict[str, DeploymentRecord] | None = None

    def __post_init__(self) -> None:
        if self.records is None:
            self.records = {}

    async def deploy(self, request: DeploymentRequest) -> DeploymentRecord:
        record = DeploymentRecord(
            id=str(uuid4()),
            provider=self.name,
            request=request,
            status="deployed",
            url=f"{self.base_url.rstrip('/')}/{request.application}/{request.environment}",
        )
        assert self.records is not None
        self.records[record.id] = record
        return record

    async def rollback(self, deployment_id: str) -> DeploymentRecord:
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
