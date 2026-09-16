"""Transactional installation, update and rollback use cases."""

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from kya_platform.application import OutboxMessage
from kya_platform.application.ports.reliability import OutboxPort
from kya_platform.domain.distribution import (
    ChangeKind,
    Installation,
    UpdatePolicy,
    ValidatedRelease,
    assess_update,
)


class InstallationNotFoundError(LookupError):
    """An installation is absent from the caller's disclosed scope."""


class InstallationRepository(Protocol):
    async def get(self, installation_id: UUID) -> Installation | None: ...

    async def save(self, installation: Installation) -> None: ...


class DistributionUnitOfWork(Protocol):
    installations: InstallationRepository
    outbox: OutboxPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class DistributionUnitOfWorkFactory(Protocol):
    def __call__(self) -> DistributionUnitOfWork: ...


class DistributionService:
    def __init__(self, unit_of_work_factory: DistributionUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def install(
        self,
        *,
        installation_id: UUID,
        target: str,
        release: ValidatedRelease,
        correlation_id: UUID,
    ) -> Installation:
        installation = Installation.install(id=installation_id, target=target, release=release)
        return await self._save(installation, "artifact.installed", correlation_id)

    async def update(
        self,
        installation_id: UUID,
        *,
        release: ValidatedRelease,
        kind: ChangeKind,
        policy: UpdatePolicy,
        approved: bool,
        correlation_id: UUID,
    ) -> Installation:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.installations, installation_id)
            decision = assess_update(policy, kind=kind, is_compatible=release.is_compatible)
            updated = current.update(release, decision=decision, approved=approved)
            await unit_of_work.installations.save(updated)
            await unit_of_work.outbox.add(self._event("artifact.updated", updated, correlation_id))
            await unit_of_work.commit()
        return updated

    async def rollback(
        self,
        installation_id: UUID,
        *,
        expected_release_id: UUID | None,
        correlation_id: UUID,
    ) -> Installation:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.installations, installation_id)
            updated = current.rollback(expected_release_id=expected_release_id)
            await unit_of_work.installations.save(updated)
            await unit_of_work.outbox.add(
                self._event("artifact.rolled_back", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    async def suspend(self, installation_id: UUID, *, correlation_id: UUID) -> Installation:
        return await self._transition(
            installation_id,
            "artifact.installation.suspended",
            correlation_id,
            "suspend",
        )

    async def resume(self, installation_id: UUID, *, correlation_id: UUID) -> Installation:
        return await self._transition(
            installation_id,
            "artifact.installation.resumed",
            correlation_id,
            "resume",
        )

    async def revoke(self, installation_id: UUID, *, correlation_id: UUID) -> Installation:
        return await self._transition(
            installation_id,
            "artifact.installation.revoked",
            correlation_id,
            "revoke",
        )

    async def _transition(
        self,
        installation_id: UUID,
        topic: str,
        correlation_id: UUID,
        action: str,
    ) -> Installation:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.installations, installation_id)
            transition = getattr(current, action)
            updated: Installation = transition()
            if updated is current:
                return current
            await unit_of_work.installations.save(updated)
            await unit_of_work.outbox.add(self._event(topic, updated, correlation_id))
            await unit_of_work.commit()
        return updated

    async def _save(
        self, installation: Installation, topic: str, correlation_id: UUID
    ) -> Installation:
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.installations.save(installation)
            await unit_of_work.outbox.add(self._event(topic, installation, correlation_id))
            await unit_of_work.commit()
        return installation

    @staticmethod
    async def _required(repository: InstallationRepository, installation_id: UUID) -> Installation:
        installation = await repository.get(installation_id)
        if installation is None:
            raise InstallationNotFoundError("installation not found")
        return installation

    @staticmethod
    def _event(topic: str, installation: Installation, correlation_id: UUID) -> OutboxMessage:
        return OutboxMessage(
            topic=topic,
            aggregate_type="installation",
            aggregate_id=str(installation.id),
            payload={
                "artifact_id": str(installation.artifact_id),
                "target": installation.target,
                "release_id": str(installation.active.release_id),
                "version": installation.active.version,
                "content_digest": installation.active.content_digest,
                "status": installation.status.value,
                "revision": installation.revision,
            },
            correlation_id=correlation_id,
        )


__all__ = [
    "DistributionService",
    "DistributionUnitOfWork",
    "DistributionUnitOfWorkFactory",
    "InstallationNotFoundError",
    "InstallationRepository",
]
