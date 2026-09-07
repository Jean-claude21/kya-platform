from dataclasses import dataclass, field
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.distribution import (
    DistributionService,
    DistributionUnitOfWorkFactory,
)
from kya_platform.domain.distribution import (
    ChangeKind,
    DistributionRuleError,
    Installation,
    InstallationStatus,
    ReleaseAvailability,
    UpdateDecision,
    UpdatePolicy,
    ValidatedRelease,
)


@dataclass
class MemoryRepository:
    records: dict[UUID, Installation] = field(default_factory=dict)

    async def get(self, installation_id: UUID) -> Installation | None:
        return self.records.get(installation_id)

    async def save(self, installation: Installation) -> None:
        self.records[installation.id] = installation


@dataclass
class MemoryOutbox:
    messages: list[OutboxMessage] = field(default_factory=list)

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


@dataclass
class MemoryUnitOfWork:
    installations: MemoryRepository
    outbox: MemoryOutbox
    committed: bool = False

    async def __aenter__(self) -> MemoryUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def release(artifact_id: UUID, version: str, *, safe: bool = True) -> ValidatedRelease:
    return ValidatedRelease(
        id=uuid4(),
        artifact_id=artifact_id,
        version=version,
        content_digest="a" * 64,
        integrity_verified=safe,
        is_compatible=safe,
    )


@pytest.mark.asyncio
async def test_install_update_and_rollback_preserve_last_known_good() -> None:
    repository = MemoryRepository()
    outbox = MemoryOutbox()
    unit_of_work = MemoryUnitOfWork(repository, outbox)
    service = DistributionService(cast(DistributionUnitOfWorkFactory, lambda: unit_of_work))
    installation_id = uuid4()
    artifact_id = uuid4()
    first = release(artifact_id, "1.0.0")
    second = release(artifact_id, "1.0.1")

    installed = await service.install(
        installation_id=installation_id,
        target="workspace:dss",
        release=first,
        correlation_id=uuid4(),
    )
    updated = await service.update(
        installation_id,
        release=second,
        kind=ChangeKind.PATCH,
        policy=UpdatePolicy(),
        approved=False,
        correlation_id=uuid4(),
    )
    rolled_back = await service.rollback(
        installation_id,
        expected_release_id=first.id,
        correlation_id=uuid4(),
    )

    assert installed.active.version == "1.0.0"
    assert updated.active.version == "1.0.1"
    assert rolled_back.active.version == "1.0.0"
    assert [message.topic for message in outbox.messages] == [
        "artifact.installed",
        "artifact.updated",
        "artifact.rolled_back",
    ]


@pytest.mark.asyncio
async def test_major_update_requires_approval() -> None:
    repository = MemoryRepository()
    unit_of_work = MemoryUnitOfWork(repository, MemoryOutbox())
    service = DistributionService(cast(DistributionUnitOfWorkFactory, lambda: unit_of_work))
    artifact_id = uuid4()
    installation_id = uuid4()
    repository.records[installation_id] = Installation.install(
        id=installation_id,
        target="workspace:dss",
        release=release(artifact_id, "1.0.0"),
    )

    with pytest.raises(DistributionRuleError, match="approval"):
        await service.update(
            installation_id,
            release=release(artifact_id, "2.0.0"),
            kind=ChangeKind.MAJOR,
            policy=UpdatePolicy(),
            approved=False,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_install_rejects_unverified_release_without_side_effect() -> None:
    repository = MemoryRepository()
    outbox = MemoryOutbox()
    service = DistributionService(
        cast(
            DistributionUnitOfWorkFactory,
            lambda: MemoryUnitOfWork(repository, outbox),
        )
    )

    with pytest.raises(DistributionRuleError, match="integrity"):
        await service.install(
            installation_id=uuid4(),
            target="workspace:dss",
            release=release(uuid4(), "1.0.0", safe=False),
            correlation_id=uuid4(),
        )

    assert repository.records == {}
    assert outbox.messages == []


@pytest.mark.asyncio
async def test_suspend_resume_and_revoke_are_audited_and_fail_closed() -> None:
    repository = MemoryRepository()
    outbox = MemoryOutbox()
    service = DistributionService(
        cast(DistributionUnitOfWorkFactory, lambda: MemoryUnitOfWork(repository, outbox))
    )
    installation_id = uuid4()
    artifact_id = uuid4()
    repository.records[installation_id] = Installation.install(
        id=installation_id,
        target="workspace:dss",
        release=release(artifact_id, "1.0.0"),
    )

    suspended = await service.suspend(installation_id, correlation_id=uuid4())
    resumed = await service.resume(installation_id, correlation_id=uuid4())
    revoked = await service.revoke(installation_id, correlation_id=uuid4())

    assert suspended.status is InstallationStatus.SUSPENDED
    assert resumed.status is InstallationStatus.ACTIVE
    assert revoked.status is InstallationStatus.REVOKED
    assert revoked.revision == 4
    assert [message.topic for message in outbox.messages] == [
        "artifact.installation.suspended",
        "artifact.installation.resumed",
        "artifact.installation.revoked",
    ]
    with pytest.raises(DistributionRuleError, match="cannot be resumed"):
        await service.resume(installation_id, correlation_id=uuid4())


@pytest.mark.parametrize(
    "availability",
    [ReleaseAvailability.SUSPENDED, ReleaseAvailability.REVOKED],
)
def test_unavailable_release_cannot_be_installed(availability: ReleaseAvailability) -> None:
    artifact_id = uuid4()
    unavailable = ValidatedRelease(
        id=uuid4(),
        artifact_id=artifact_id,
        version="1.0.0",
        content_digest="a" * 64,
        integrity_verified=True,
        is_compatible=True,
        availability=availability,
    )

    with pytest.raises(DistributionRuleError, match=availability.value):
        Installation.install(id=uuid4(), target="workspace:dss", release=unavailable)


def test_lifecycle_idempotence_and_terminal_guards() -> None:
    artifact_id = uuid4()
    first = release(artifact_id, "1.0.0")
    installed = Installation.install(id=uuid4(), target="workspace:dss", release=first)

    assert installed.update(first, decision=UpdateDecision.PROPOSE, approved=False) is installed
    assert installed.resume() is installed
    suspended = installed.suspend()
    assert suspended.suspend() is suspended
    revoked = suspended.revoke()
    assert revoked.revoke() is revoked
    with pytest.raises(DistributionRuleError, match="active installation"):
        suspended.update(
            release(artifact_id, "1.0.1"),
            decision=UpdateDecision.PROPOSE,
            approved=False,
        )
    with pytest.raises(DistributionRuleError, match="last-known-good"):
        installed.rollback()

    incompatible = ValidatedRelease(
        id=uuid4(),
        artifact_id=artifact_id,
        version="1.1.0",
        content_digest="a" * 64,
        integrity_verified=True,
        is_compatible=False,
    )
    with pytest.raises(DistributionRuleError, match="incompatible"):
        incompatible.require_safe()
