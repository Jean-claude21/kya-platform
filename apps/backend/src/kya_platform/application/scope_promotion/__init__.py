"""Widen an artifact's visibility scope; never narrow it, never duplicate the artifact.

A scope promotion reuses the same review/approval separation-of-duties machine as publication
(see `application.publication`), but its outcome only ever widens `visibility_scope_unit_id` on
the existing artifact row. The candidate target unit must be a real ancestor of the current scope
in the organizational hierarchy (verified through the same OpenFGA `ancestor` relation used
elsewhere), never an unrelated or narrower unit.
"""

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from kya_platform.application import OutboxMessage
from kya_platform.application.ports.reliability import OutboxPort
from kya_platform.authorization import AuthorizationPort, CheckRequest
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ReviewDecision,
    ScopePromotionRequest,
)


class ScopePromotionNotFoundError(LookupError):
    """A scope promotion request does not exist in the caller's disclosed scope."""


class ScopePromotionNotAncestorError(ValueError):
    """The requested target unit is not an ancestor of the artifact's current scope."""


class ScopePromotionRepository(Protocol):
    async def get(self, request_id: UUID) -> ScopePromotionRequest | None:
        """Load one scope promotion request in the active transaction."""

    async def save(self, request: ScopePromotionRequest) -> None:
        """Insert or update one request; applying it also widens the artifact's scope."""


class ScopePromotionUnitOfWork(Protocol):
    promotions: ScopePromotionRepository
    outbox: OutboxPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ScopePromotionUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopePromotionUnitOfWork: ...


class ScopePromotionService:
    def __init__(
        self,
        unit_of_work_factory: ScopePromotionUnitOfWorkFactory,
        authorization: AuthorizationPort,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorization = authorization

    async def submit(
        self,
        *,
        request_id: UUID,
        artifact_id: UUID,
        current_scope_unit_id: UUID,
        target_scope_unit_id: UUID,
        requested_by: UUID,
        at: datetime,
        correlation_id: UUID,
    ) -> ScopePromotionRequest:
        if current_scope_unit_id == target_scope_unit_id:
            raise ValueError("scope promotion must target a different, wider unit")
        decision = await self._authorization.check(
            CheckRequest(
                user=f"org_unit:{target_scope_unit_id}",
                relation="ancestor",
                object=f"org_unit:{current_scope_unit_id}",
            )
        )
        if not decision.allowed:
            raise ScopePromotionNotAncestorError(
                "target scope unit is not an ancestor of the artifact's current scope"
            )
        request = ScopePromotionRequest.open(
            id=request_id,
            artifact_id=artifact_id,
            current_scope_unit_id=current_scope_unit_id,
            target_scope_unit_id=target_scope_unit_id,
            requested_by=requested_by,
            requested_at=at,
        )
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.promotions.save(request)
            await unit_of_work.outbox.add(
                self._event("scope_promotion.requested", request, correlation_id)
            )
            await unit_of_work.commit()
        return request

    async def review(
        self,
        request_id: UUID,
        *,
        actor_id: UUID,
        decision: ReviewDecision,
        at: datetime,
        correlation_id: UUID,
    ) -> ScopePromotionRequest:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.promotions, request_id)
            updated = current.review(actor_id, decision, at=at)
            await unit_of_work.promotions.save(updated)
            await unit_of_work.outbox.add(
                self._event("scope_promotion.reviewed", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    async def approve(
        self,
        request_id: UUID,
        *,
        actor_id: UUID,
        decision: ApprovalDecision,
        at: datetime,
        correlation_id: UUID,
    ) -> ScopePromotionRequest:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.promotions, request_id)
            updated = current.approve(actor_id, decision, at=at)
            await unit_of_work.promotions.save(updated)
            await unit_of_work.outbox.add(
                self._event("scope_promotion.approved", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    async def apply(
        self,
        request_id: UUID,
        *,
        actor_id: UUID,
        at: datetime,
        correlation_id: UUID,
    ) -> ScopePromotionRequest:
        """Apply an approved promotion; the repository widens the artifact's scope atomically."""

        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.promotions, request_id)
            updated = current.apply(actor_id, at=at)
            await unit_of_work.promotions.save(updated)
            await unit_of_work.outbox.add(
                self._event("scope_promotion.applied", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    @staticmethod
    async def _required(
        repository: ScopePromotionRepository, request_id: UUID
    ) -> ScopePromotionRequest:
        request = await repository.get(request_id)
        if request is None:
            raise ScopePromotionNotFoundError("scope promotion request not found")
        return request

    @staticmethod
    def _event(topic: str, request: ScopePromotionRequest, correlation_id: UUID) -> OutboxMessage:
        return OutboxMessage(
            topic=topic,
            aggregate_type="scope_promotion",
            aggregate_id=str(request.id),
            payload={
                "artifact_id": str(request.artifact_id),
                "current_scope_unit_id": str(request.current_scope_unit_id),
                "target_scope_unit_id": str(request.target_scope_unit_id),
                "status": request.status.value,
            },
            correlation_id=correlation_id,
        )


__all__ = [
    "ScopePromotionNotAncestorError",
    "ScopePromotionNotFoundError",
    "ScopePromotionRepository",
    "ScopePromotionService",
    "ScopePromotionUnitOfWork",
    "ScopePromotionUnitOfWorkFactory",
]
