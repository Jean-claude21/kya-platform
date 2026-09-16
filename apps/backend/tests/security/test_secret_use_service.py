"""Secret grants remain scoped, temporary, revocable and safe to audit."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID, uuid7

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.secrets import (
    SecretGrantStatus,
    SecretUseDeniedError,
    SecretUseGrant,
    SecretUseService,
)
from kya_platform.domain.organization import DateRange
from kya_platform.secrets import SecretKind, SecretReference, SecretStatus

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
REQUESTER = UUID("019914b2-1a40-7000-8000-000000000041")
APPROVER = UUID("019914b2-1a40-7000-8000-000000000042")
CORRELATION = UUID("019914b2-1a40-7000-8000-000000000043")


class MemoryReferences:
    def __init__(self, reference: SecretReference) -> None:
        self.reference = reference

    async def get(self, reference_id: UUID) -> SecretReference | None:
        return self.reference if reference_id == self.reference.id else None

    async def list_for_scope(self, owner_scope: str) -> tuple[SecretReference, ...]:
        return (self.reference,) if owner_scope == self.reference.owner_scope else ()

    async def register(self, reference: SecretReference) -> None:
        self.reference = reference

    async def revoke(self, reference_id: UUID) -> None:
        if reference_id == self.reference.id:
            self.reference = self.reference.model_copy(update={"status": SecretStatus.REVOKED})


class MemoryGrants:
    def __init__(self) -> None:
        self.items: dict[UUID, SecretUseGrant] = {}

    async def get(self, grant_id: UUID) -> SecretUseGrant | None:
        return self.items.get(grant_id)

    async def save(self, grant: SecretUseGrant) -> None:
        self.items[grant.id] = grant


class MemoryOutbox:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    async def add(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class MemoryUnitOfWork:
    def __init__(self, reference: SecretReference) -> None:
        self.references = MemoryReferences(reference)
        self.grants = MemoryGrants()
        self.outbox = MemoryOutbox()
        self.commits = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def reference(*, environment: str = "preview") -> SecretReference:
    return SecretReference(
        id=uuid7(),
        provider="infisical",
        locator="project-kya/preview/integrations",
        key_name="FRAPPE_API_SECRET",
        owner_scope="workspace:platform",
        purpose="Lire les clients autorisés",
        environment=environment,
        status=SecretStatus.ACTIVE,
        created_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )


def grant(secret: SecretReference) -> SecretUseGrant:
    return SecretUseGrant(
        id=uuid7(),
        reference_id=secret.id,
        requested_by=REQUESTER,
        beneficiary="service:frappe-reader",
        purpose=secret.purpose,
        owner_scope=secret.owner_scope,
        environment=secret.environment,
        validity=DateRange(NOW, NOW + timedelta(hours=1)),
        status=SecretGrantStatus.REQUESTED,
        requested_at=NOW,
    )


async def approved_service() -> tuple[SecretUseService, MemoryUnitOfWork, SecretUseGrant]:
    secret = reference()
    unit_of_work = MemoryUnitOfWork(secret)
    service = SecretUseService(lambda: unit_of_work)
    current = grant(secret)
    await service.request(current, correlation_id=CORRELATION)
    current = await service.decide(
        current.id,
        actor_id=APPROVER,
        approved=True,
        at=NOW + timedelta(minutes=1),
        correlation_id=CORRELATION,
    )
    return service, unit_of_work, current


@pytest.mark.security
@pytest.mark.asyncio
async def test_preview_grant_cannot_cross_environment_scope_purpose_or_beneficiary() -> None:
    service, unit_of_work, current = await approved_service()
    cases = (
        {"environment": "production"},
        {"owner_scope": "workspace:other"},
        {"purpose": "Administrer Frappe"},
        {"beneficiary": "service:other"},
    )

    defaults = {
        "beneficiary": current.beneficiary,
        "purpose": current.purpose,
        "owner_scope": current.owner_scope,
        "environment": current.environment,
    }
    for override in cases:
        with pytest.raises(SecretUseDeniedError):
            await service.authorize_use(
                current.id,
                **(defaults | override),
                at=NOW + timedelta(minutes=2),
                correlation_id=CORRELATION,
            )

    assert all(
        message.topic == "secret.use.denied" for message in unit_of_work.outbox.messages[-4:]
    )


@pytest.mark.security
@pytest.mark.asyncio
async def test_expired_grant_is_denied_and_produces_actionable_reason() -> None:
    service, unit_of_work, current = await approved_service()

    with pytest.raises(SecretUseDeniedError) as denied:
        await service.authorize_use(
            current.id,
            beneficiary=current.beneficiary,
            purpose=current.purpose,
            owner_scope=current.owner_scope,
            environment=current.environment,
            at=NOW + timedelta(hours=1),
            correlation_id=CORRELATION,
        )

    assert denied.value.reason == "grant_expired"
    assert unit_of_work.outbox.messages[-1].payload["reason"] == "grant_expired"


@pytest.mark.security
@pytest.mark.asyncio
async def test_emergency_revocation_blocks_next_use_immediately() -> None:
    service, _unit_of_work, current = await approved_service()
    revoked = await service.revoke(
        current.id,
        actor_id=APPROVER,
        at=NOW + timedelta(minutes=2),
        correlation_id=CORRELATION,
    )

    with pytest.raises(SecretUseDeniedError) as denied:
        await service.authorize_use(
            current.id,
            beneficiary=current.beneficiary,
            purpose=current.purpose,
            owner_scope=current.owner_scope,
            environment=current.environment,
            at=NOW + timedelta(minutes=3),
            correlation_id=CORRELATION,
        )

    assert revoked.status is SecretGrantStatus.REVOKED
    assert denied.value.reason == "grant_inactive"


@pytest.mark.security
@pytest.mark.asyncio
async def test_authorized_receipt_and_audit_never_contain_secret_value() -> None:
    service, unit_of_work, current = await approved_service()
    receipt = await service.authorize_use(
        current.id,
        beneficiary=current.beneficiary,
        purpose=current.purpose,
        owner_scope=current.owner_scope,
        environment=current.environment,
        at=NOW + timedelta(minutes=2),
        correlation_id=CORRELATION,
    )

    serialized = f"{receipt!r} {unit_of_work.outbox.messages!r}"
    assert receipt.key_name == "FRAPPE_API_SECRET"
    assert "secret-value" not in serialized
    assert "value" not in unit_of_work.outbox.messages[-1].payload


@pytest.mark.security
@pytest.mark.asyncio
async def test_requester_cannot_approve_own_request() -> None:
    secret = reference()
    unit_of_work = MemoryUnitOfWork(secret)
    service = SecretUseService(lambda: unit_of_work)
    current = grant(secret)
    await service.request(current, correlation_id=CORRELATION)

    with pytest.raises(PermissionError, match="own secret access"):
        await service.decide(
            current.id,
            actor_id=REQUESTER,
            approved=True,
            at=NOW + timedelta(minutes=1),
            correlation_id=CORRELATION,
        )


@pytest.mark.security
@pytest.mark.asyncio
async def test_personal_secret_cannot_be_shared_as_team_identity() -> None:
    secret = reference().model_copy(
        update={"kind": SecretKind.PERSONAL, "owner_scope": f"principal:{REQUESTER}"}
    )
    unit_of_work = MemoryUnitOfWork(secret)
    service = SecretUseService(lambda: unit_of_work)
    current = grant(secret)

    with pytest.raises(ValueError, match="personal secret cannot be shared"):
        await service.request(current, correlation_id=CORRELATION)
