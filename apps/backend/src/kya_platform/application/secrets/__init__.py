"""Approval and use orchestration for externally stored secrets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from kya_platform.application import OutboxMessage
from kya_platform.application.ports.reliability import OutboxPort
from kya_platform.domain.organization import DateRange
from kya_platform.secrets import SecretKind, SecretReference, SecretReferencePort, SecretStatus


class SecretGrantStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class SecretUseGrant:
    """Governance decision only; this object can never carry secret material."""

    id: UUID
    reference_id: UUID
    requested_by: UUID
    beneficiary: str
    purpose: str
    owner_scope: str
    environment: str
    validity: DateRange
    status: SecretGrantStatus
    requested_at: datetime
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    revoked_by: UUID | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.beneficiary, self.purpose, self.owner_scope, self.environment)
        ):
            raise ValueError("beneficiary, purpose, scope and environment are required")
        if self.environment not in {"local", "preview", "test", "production"}:
            raise ValueError("unsupported secret environment")
        if self.requested_at != self.validity.valid_from:
            raise ValueError("grant validity must start when the request is created")

    def decide(self, actor_id: UUID, *, approved: bool, at: datetime) -> SecretUseGrant:
        if self.status is not SecretGrantStatus.REQUESTED:
            raise ValueError("secret-use request is already decided")
        if actor_id == self.requested_by:
            raise PermissionError("requester cannot approve their own secret access")
        if not self.validity.contains(at):
            raise ValueError("secret-use request has expired")
        return replace(
            self,
            status=SecretGrantStatus.APPROVED if approved else SecretGrantStatus.REJECTED,
            decided_by=actor_id,
            decided_at=at,
        )

    def revoke(self, actor_id: UUID, *, at: datetime) -> SecretUseGrant:
        if self.status is SecretGrantStatus.REVOKED:
            return self
        return replace(
            self,
            status=SecretGrantStatus.REVOKED,
            revoked_by=actor_id,
            revoked_at=at,
        )


@dataclass(frozen=True, slots=True)
class AuthorizedSecretUse:
    """Receipt allowing a broker to resolve one value; contains no value itself."""

    grant_id: UUID
    reference_id: UUID
    beneficiary: str
    locator: str
    key_name: str
    environment: str
    expires_at: datetime


class SecretUseDeniedError(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__("secret use denied")
        self.reason = reason


class SecretUseGrantRepository(Protocol):
    async def get(self, grant_id: UUID) -> SecretUseGrant | None: ...

    async def save(self, grant: SecretUseGrant) -> None: ...


class SecretUseUnitOfWork(Protocol):
    grants: SecretUseGrantRepository
    references: SecretReferencePort
    outbox: OutboxPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class SecretUseUnitOfWorkFactory(Protocol):
    def __call__(self) -> SecretUseUnitOfWork: ...


class SecretUseService:
    def __init__(self, unit_of_work_factory: SecretUseUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def request(self, grant: SecretUseGrant, *, correlation_id: UUID) -> SecretUseGrant:
        async with self._unit_of_work_factory() as unit_of_work:
            reference = await unit_of_work.references.get(grant.reference_id)
            if reference is None:
                raise LookupError("secret reference not found")
            self._validate_binding(grant, reference)
            await unit_of_work.grants.save(grant)
            await unit_of_work.outbox.add(
                self._event("secret.use.requested", grant, correlation_id)
            )
            await unit_of_work.commit()
        return grant

    async def decide(
        self,
        grant_id: UUID,
        *,
        actor_id: UUID,
        approved: bool,
        at: datetime,
        correlation_id: UUID,
    ) -> SecretUseGrant:
        async with self._unit_of_work_factory() as unit_of_work:
            grant = await self._required(unit_of_work.grants, grant_id)
            updated = grant.decide(actor_id, approved=approved, at=at)
            await unit_of_work.grants.save(updated)
            topic = "secret.use.approved" if approved else "secret.use.rejected"
            await unit_of_work.outbox.add(self._event(topic, updated, correlation_id))
            await unit_of_work.commit()
        return updated

    async def authorize_use(
        self,
        grant_id: UUID,
        *,
        beneficiary: str,
        purpose: str,
        owner_scope: str,
        environment: str,
        at: datetime,
        correlation_id: UUID,
    ) -> AuthorizedSecretUse:
        async with self._unit_of_work_factory() as unit_of_work:
            grant = await self._required(unit_of_work.grants, grant_id)
            reference = await unit_of_work.references.get(grant.reference_id)
            reason = self._denial_reason(
                grant,
                reference,
                beneficiary=beneficiary,
                purpose=purpose,
                owner_scope=owner_scope,
                environment=environment,
                at=at,
            )
            if reason is not None:
                await unit_of_work.outbox.add(
                    self._event("secret.use.denied", grant, correlation_id, reason=reason)
                )
                await unit_of_work.commit()
                raise SecretUseDeniedError(reason)
            assert reference is not None
            assert grant.validity.valid_until is not None
            receipt = AuthorizedSecretUse(
                grant.id,
                reference.id,
                grant.beneficiary,
                reference.locator,
                reference.key_name,
                grant.environment,
                grant.validity.valid_until,
            )
            await unit_of_work.outbox.add(
                self._event("secret.use.authorized", grant, correlation_id)
            )
            await unit_of_work.commit()
            return receipt

    async def revoke(
        self,
        grant_id: UUID,
        *,
        actor_id: UUID,
        at: datetime,
        correlation_id: UUID,
    ) -> SecretUseGrant:
        async with self._unit_of_work_factory() as unit_of_work:
            grant = await self._required(unit_of_work.grants, grant_id)
            updated = grant.revoke(actor_id, at=at)
            await unit_of_work.grants.save(updated)
            await unit_of_work.outbox.add(
                self._event("secret.use.revoked", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    @staticmethod
    def _validate_binding(grant: SecretUseGrant, reference: SecretReference) -> None:
        if (
            grant.owner_scope != reference.owner_scope
            or grant.environment != reference.environment
            or grant.purpose != reference.purpose
        ):
            raise ValueError("grant scope, environment and purpose must match the secret reference")
        if reference.kind is SecretKind.PERSONAL and grant.beneficiary != reference.owner_scope:
            raise ValueError("a personal secret cannot be shared with another beneficiary")
        if grant.validity.valid_until is None:
            raise ValueError("secret-use grants must expire")

    @staticmethod
    def _denial_reason(
        grant: SecretUseGrant,
        reference: SecretReference | None,
        *,
        beneficiary: str,
        purpose: str,
        owner_scope: str,
        environment: str,
        at: datetime,
    ) -> str | None:
        if reference is None:
            return "reference_missing"
        if grant.status is not SecretGrantStatus.APPROVED:
            return "grant_inactive"
        if reference.status is not SecretStatus.ACTIVE:
            return "reference_inactive"
        if reference.expires_at is not None and at >= reference.expires_at:
            return "reference_expired"
        if not grant.validity.contains(at):
            return "grant_expired"
        if beneficiary != grant.beneficiary:
            return "beneficiary_mismatch"
        if purpose != grant.purpose:
            return "purpose_mismatch"
        if owner_scope != grant.owner_scope:
            return "scope_mismatch"
        if environment != grant.environment:
            return "environment_mismatch"
        return None

    @staticmethod
    async def _required(repository: SecretUseGrantRepository, grant_id: UUID) -> SecretUseGrant:
        grant = await repository.get(grant_id)
        if grant is None:
            raise LookupError("secret-use grant not found")
        return grant

    @staticmethod
    def _event(
        topic: str,
        grant: SecretUseGrant,
        correlation_id: UUID,
        *,
        reason: str | None = None,
    ) -> OutboxMessage:
        payload = {
            "reference_id": str(grant.reference_id),
            "beneficiary": grant.beneficiary,
            "purpose": grant.purpose,
            "owner_scope": grant.owner_scope,
            "environment": grant.environment,
            "status": grant.status.value,
        }
        if reason is not None:
            payload["reason"] = reason
        return OutboxMessage(
            topic=topic,
            aggregate_type="secret_use_grant",
            aggregate_id=str(grant.id),
            payload=payload,
            correlation_id=correlation_id,
        )


__all__ = [
    "AuthorizedSecretUse",
    "SecretGrantStatus",
    "SecretUseDeniedError",
    "SecretUseGrant",
    "SecretUseGrantRepository",
    "SecretUseService",
    "SecretUseUnitOfWork",
    "SecretUseUnitOfWorkFactory",
]
