"""Transactional publication use cases."""

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from kya_platform.application import OutboxMessage
from kya_platform.application.ports.reliability import OutboxPort
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    ReviewDecision,
)


class PublicationNotFoundError(LookupError):
    """A publication request does not exist in the caller's disclosed scope."""


class PublicationRepository(Protocol):
    async def get(self, request_id: UUID) -> PublicationRequest | None:
        """Load one request in the active transaction."""

    async def save(self, request: PublicationRequest) -> None:
        """Insert or update one request with optimistic concurrency."""


class PublicationUnitOfWork(Protocol):
    publications: PublicationRepository
    outbox: OutboxPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class PublicationUnitOfWorkFactory(Protocol):
    def __call__(self) -> PublicationUnitOfWork: ...


class PublicationService:
    def __init__(self, unit_of_work_factory: PublicationUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def submit(
        self,
        *,
        request_id: UUID,
        candidate: ArtifactVersion,
        actor_id: UUID,
        at: datetime,
        correlation_id: UUID,
        separation_of_duties: bool = True,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> PublicationRequest:
        request = PublicationRequest.open(
            id=request_id,
            candidate=candidate,
            requested_by=actor_id,
            requested_at=at,
            separation_of_duties=separation_of_duties,
            evidence_ids=evidence_ids,
        )
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.publications.save(request)
            await unit_of_work.outbox.add(
                self._event("publication.requested", request, correlation_id)
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
    ) -> PublicationRequest:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.publications, request_id)
            updated = current.review(actor_id, decision, at=at)
            await unit_of_work.publications.save(updated)
            await unit_of_work.outbox.add(
                self._event("publication.reviewed", updated, correlation_id)
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
    ) -> PublicationRequest:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.publications, request_id)
            updated = current.approve(actor_id, decision, at=at)
            await unit_of_work.publications.save(updated)
            await unit_of_work.outbox.add(
                self._event("publication.approved", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    async def publish(
        self,
        request_id: UUID,
        *,
        actor_id: UUID,
        content_digest: str,
        at: datetime,
        correlation_id: UUID,
    ) -> PublicationRequest:
        async with self._unit_of_work_factory() as unit_of_work:
            current = await self._required(unit_of_work.publications, request_id)
            updated = current.mark_published(actor_id, content_digest=content_digest, at=at)
            await unit_of_work.publications.save(updated)
            await unit_of_work.outbox.add(
                self._event("artifact.published", updated, correlation_id)
            )
            await unit_of_work.commit()
        return updated

    @staticmethod
    async def _required(repository: PublicationRepository, request_id: UUID) -> PublicationRequest:
        request = await repository.get(request_id)
        if request is None:
            raise PublicationNotFoundError("publication request not found")
        return request

    @staticmethod
    def _event(topic: str, request: PublicationRequest, correlation_id: UUID) -> OutboxMessage:
        return OutboxMessage(
            topic=topic,
            aggregate_type="publication_request",
            aggregate_id=str(request.id),
            payload={
                "artifact_id": str(request.candidate.artifact_id),
                "version": request.candidate.version,
                "content_digest": request.candidate.content_digest,
                "status": request.status.value,
            },
            correlation_id=correlation_id,
        )


__all__ = [
    "PublicationNotFoundError",
    "PublicationRepository",
    "PublicationService",
    "PublicationUnitOfWork",
    "PublicationUnitOfWorkFactory",
]
