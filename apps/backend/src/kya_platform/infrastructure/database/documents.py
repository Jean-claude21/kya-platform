"""Transactional Neon adapter for the native document runtime."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.documents import DocumentConflictError, DocumentNotFoundError
from kya_platform.domain.documents import (
    DocumentDefinition,
    DocumentEvidence,
    DocumentRecord,
    DocumentRevision,
    DocumentValue,
    EvidenceKind,
)
from kya_platform.infrastructure.database.models.documents import (
    DocumentDefinitionRow,
    DocumentEvidenceRow,
    DocumentRecordRow,
    DocumentRevisionRow,
)


def _definition(row: DocumentDefinitionRow) -> DocumentDefinition:
    return DocumentDefinition(
        id=row.id,
        public_id=row.public_id,
        version=row.version,
        owner_scope=row.owner_scope,
        release_id=row.release_id,
        definition=cast(dict[str, DocumentValue], row.definition),
        digest=row.digest,
        published_by=row.published_by,
        published_at=row.published_at,
    )


def _record(row: DocumentRecordRow) -> DocumentRecord:
    return DocumentRecord(
        id=row.id,
        definition_id=row.definition_id,
        owner_scope=row.owner_scope,
        state=row.state,
        current_revision=row.current_revision,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _revision(row: DocumentRevisionRow) -> DocumentRevision:
    return DocumentRevision(
        record_id=row.record_id,
        revision=row.revision,
        payload=cast(dict[str, DocumentValue], row.payload),
        digest=row.digest,
        authored_by=row.authored_by,
        created_at=row.created_at,
    )


def _evidence(row: DocumentEvidenceRow) -> DocumentEvidence:
    return DocumentEvidence(
        id=row.id,
        record_id=row.record_id,
        revision=row.revision,
        kind=EvidenceKind(row.kind),
        actor_id=row.actor_id,
        evidence=cast(dict[str, DocumentValue], row.evidence),
        digest=row.digest,
        occurred_at=row.occurred_at,
    )


class SqlAlchemyDocumentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def publish_definition(self, definition: DocumentDefinition) -> DocumentDefinition:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(DocumentDefinitionRow).where(
                    DocumentDefinitionRow.public_id == definition.public_id,
                    DocumentDefinitionRow.version == definition.version,
                )
            )
            if existing is not None:
                if (
                    existing.digest != definition.digest
                    or existing.release_id != definition.release_id
                ):
                    raise DocumentConflictError(
                        "document definition identity already has different immutable content"
                    )
                return _definition(existing)
            session.add(
                DocumentDefinitionRow(
                    id=definition.id,
                    public_id=definition.public_id,
                    version=definition.version,
                    owner_scope=definition.owner_scope,
                    release_id=definition.release_id,
                    definition=dict(definition.definition),
                    digest=definition.digest,
                    published_by=definition.published_by,
                    published_at=definition.published_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise DocumentConflictError(
                    "document definition conflicts with an immutable row"
                ) from error
            return definition

    async def get_definition(self, public_id: str, version: str) -> DocumentDefinition | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentDefinitionRow).where(
                    DocumentDefinitionRow.public_id == public_id,
                    DocumentDefinitionRow.version == version,
                )
            )
            return _definition(row) if row is not None else None

    async def create_record(
        self, record: DocumentRecord, revision: DocumentRevision
    ) -> DocumentRecord:
        if revision.record_id != record.id or revision.revision != record.current_revision:
            raise DocumentConflictError("initial record and revision do not agree")
        async with self._sessions() as session:
            definition = await session.get(DocumentDefinitionRow, record.definition_id)
            if definition is None:
                raise DocumentNotFoundError("document definition does not exist")
            if definition.owner_scope != record.owner_scope:
                raise DocumentConflictError("record scope must match its definition scope")
            session.add_all(
                [
                    DocumentRecordRow(
                        id=record.id,
                        definition_id=record.definition_id,
                        owner_scope=record.owner_scope,
                        state=record.state,
                        current_revision=record.current_revision,
                        created_by=record.created_by,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                    ),
                    DocumentRevisionRow(
                        record_id=revision.record_id,
                        revision=revision.revision,
                        payload=dict(revision.payload),
                        digest=revision.digest,
                        authored_by=revision.authored_by,
                        created_at=revision.created_at,
                    ),
                ]
            )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise DocumentConflictError("document record already exists") from error
            return record

    async def get_record(
        self, record_id: UUID, *, owner_scope: str
    ) -> tuple[DocumentRecord, DocumentRevision] | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentRecordRow).where(
                    DocumentRecordRow.id == record_id,
                    DocumentRecordRow.owner_scope == owner_scope,
                )
            )
            if row is None:
                return None
            revision = await session.get(DocumentRevisionRow, (row.id, row.current_revision))
            if revision is None:
                raise RuntimeError("document current revision is missing")
            return _record(row), _revision(revision)

    async def append_revision(
        self,
        revision: DocumentRevision,
        *,
        owner_scope: str,
        expected_revision: int,
        state: str,
    ) -> DocumentRecord:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentRecordRow)
                .where(
                    DocumentRecordRow.id == revision.record_id,
                    DocumentRecordRow.owner_scope == owner_scope,
                )
                .with_for_update()
            )
            if row is None:
                raise DocumentNotFoundError("document record does not exist")
            if (
                row.current_revision != expected_revision
                or revision.revision != expected_revision + 1
            ):
                raise DocumentConflictError("document revision changed concurrently")
            session.add(
                DocumentRevisionRow(
                    record_id=revision.record_id,
                    revision=revision.revision,
                    payload=dict(revision.payload),
                    digest=revision.digest,
                    authored_by=revision.authored_by,
                    created_at=revision.created_at,
                )
            )
            row.current_revision = revision.revision
            row.state = state
            row.updated_at = revision.created_at
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise DocumentConflictError(
                    "document revision conflicts with immutable history"
                ) from error
            return _record(row)

    async def append_evidence(
        self, evidence: DocumentEvidence, *, owner_scope: str
    ) -> DocumentEvidence:
        async with self._sessions() as session:
            record = await session.scalar(
                select(DocumentRecordRow).where(
                    DocumentRecordRow.id == evidence.record_id,
                    DocumentRecordRow.owner_scope == owner_scope,
                )
            )
            if record is None:
                raise DocumentNotFoundError("document record does not exist")
            if evidence.revision > record.current_revision:
                raise DocumentConflictError("evidence cannot target a future revision")
            session.add(
                DocumentEvidenceRow(
                    id=evidence.id,
                    record_id=evidence.record_id,
                    revision=evidence.revision,
                    kind=evidence.kind.value,
                    actor_id=evidence.actor_id,
                    evidence=dict(evidence.evidence),
                    digest=evidence.digest,
                    occurred_at=evidence.occurred_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise DocumentConflictError(
                    "evidence already exists in immutable history"
                ) from error
            return evidence

    async def list_evidence(
        self, record_id: UUID, *, owner_scope: str
    ) -> Sequence[DocumentEvidence]:
        async with self._sessions() as session:
            visible = await session.scalar(
                select(DocumentRecordRow.id).where(
                    DocumentRecordRow.id == record_id,
                    DocumentRecordRow.owner_scope == owner_scope,
                )
            )
            if visible is None:
                return ()
            rows = await session.scalars(
                select(DocumentEvidenceRow)
                .where(DocumentEvidenceRow.record_id == record_id)
                .order_by(DocumentEvidenceRow.occurred_at, DocumentEvidenceRow.id)
            )
            return tuple(_evidence(row) for row in rows)


__all__ = ["SqlAlchemyDocumentRepository"]
