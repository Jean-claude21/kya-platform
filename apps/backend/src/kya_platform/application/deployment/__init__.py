"""Provider-neutral promotion and rollback orchestration."""

from uuid import UUID

from kya_platform.infrastructure.deployment import (
    DeploymentProvider,
    DeploymentRecord,
    DeploymentRequest,
)


class PromotionService:
    def __init__(self, providers: dict[str, DeploymentProvider]) -> None:
        self._providers = providers

    async def promote(self, provider: str, request: DeploymentRequest) -> DeploymentRecord:
        adapter = self._providers.get(provider)
        if adapter is None:
            raise ValueError(f"unknown deployment provider: {provider}")
        return await adapter.deploy(request)

    async def rollback(self, provider: str, deployment_id: UUID) -> DeploymentRecord:
        adapter = self._providers.get(provider)
        if adapter is None:
            raise ValueError(f"unknown deployment provider: {provider}")
        return await adapter.rollback(deployment_id)


__all__ = ["PromotionService"]
