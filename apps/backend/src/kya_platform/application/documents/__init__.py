"""Application boundary for immutable document definitions and versioned records."""

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from kya_platform.application.documents.runtime import TransitionPlan
from kya_platform.domain.documents import (
    DocumentDefinition,
    DocumentEvidence,
    DocumentRecord,
    DocumentRevision,
    DocumentValue,
)


class DocumentConflictError(ValueError):
    """A supposedly immutable identity or revision already carries different content."""


class DocumentNotFoundError(LookupError):
    """A definition or record is absent from the authorized scope."""


class DocumentRepository(Protocol):
    async def publish_definition(self, definition: DocumentDefinition) -> DocumentDefinition: ...

    async def get_definition(self, public_id: str, version: str) -> DocumentDefinition | None: ...

    async def get_definition_by_id(self, definition_id: UUID) -> DocumentDefinition | None: ...

    async def create_record(
        self, record: DocumentRecord, revision: DocumentRevision
    ) -> DocumentRecord: ...

    async def get_record(
        self, record_id: UUID, *, owner_scope: str
    ) -> tuple[DocumentRecord, DocumentRevision] | None: ...

    async def append_revision(
        self,
        revision: DocumentRevision,
        *,
        owner_scope: str,
        expected_revision: int,
        state: str,
    ) -> DocumentRecord: ...

    async def append_evidence(
        self, evidence: DocumentEvidence, *, owner_scope: str
    ) -> DocumentEvidence: ...

    async def list_evidence(
        self, record_id: UUID, *, owner_scope: str
    ) -> Sequence[DocumentEvidence]: ...

    async def commit_transition(
        self,
        plan: TransitionPlan,
        *,
        owner_scope: str,
        correlation_id: UUID,
    ) -> DocumentRecord: ...


class DocumentService:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def publish_definition(self, definition: DocumentDefinition) -> DocumentDefinition:
        return await self._repository.publish_definition(definition)

    async def create(
        self,
        *,
        record: DocumentRecord,
        revision: DocumentRevision,
        definition_public_id: str,
        definition_version: str,
    ) -> DocumentRecord:
        definition = await self._repository.get_definition(definition_public_id, definition_version)
        if definition is None or definition.id != record.definition_id:
            raise DocumentNotFoundError("published document definition is unavailable")
        if revision.record_id != record.id or revision.revision != 1:
            raise DocumentConflictError("initial revision does not match the record")
        return await self._repository.create_record(record, revision)

    async def revise(
        self,
        *,
        revision: DocumentRevision,
        owner_scope: str,
        expected_revision: int,
        state: str,
    ) -> DocumentRecord:
        if revision.revision != expected_revision + 1:
            raise DocumentConflictError("next revision must immediately follow expected_revision")
        return await self._repository.append_revision(
            revision,
            owner_scope=owner_scope,
            expected_revision=expected_revision,
            state=state,
        )

    async def evidence(self, evidence: DocumentEvidence, *, owner_scope: str) -> DocumentEvidence:
        current = await self._repository.get_record(evidence.record_id, owner_scope=owner_scope)
        if current is None:
            raise DocumentNotFoundError("document record is unavailable")
        record, _revision = current
        if evidence.revision > record.current_revision:
            raise DocumentConflictError("evidence cannot target a future revision")
        return await self._repository.append_evidence(evidence, owner_scope=owner_scope)

    async def get(
        self, record_id: UUID, *, owner_scope: str
    ) -> tuple[DocumentRecord, DocumentRevision] | None:
        return await self._repository.get_record(record_id, owner_scope=owner_scope)

    async def get_definition(self, public_id: str, version: str) -> DocumentDefinition | None:
        return await self._repository.get_definition(public_id, version)

    async def get_definition_by_internal_id(self, definition_id: UUID) -> DocumentDefinition | None:
        return await self._repository.get_definition_by_id(definition_id)

    async def history(self, record_id: UUID, *, owner_scope: str) -> Sequence[DocumentEvidence]:
        return await self._repository.list_evidence(record_id, owner_scope=owner_scope)

    async def transition(
        self,
        plan: TransitionPlan,
        *,
        owner_scope: str,
        correlation_id: UUID,
    ) -> DocumentRecord:
        return await self._repository.commit_transition(
            plan, owner_scope=owner_scope, correlation_id=correlation_id
        )


def definition_document(value: Mapping[str, DocumentValue]) -> dict[str, object]:
    """Materialize a validated mapping for JSONB persistence."""

    return dict(value)


__all__ = [
    "DocumentConflictError",
    "DocumentNotFoundError",
    "DocumentRepository",
    "DocumentService",
    "definition_document",
]
