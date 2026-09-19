"""Document service enforces definition, revision and evidence boundaries."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.documents import (
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentService,
)
from kya_platform.domain.documents import (
    DocumentDefinition,
    DocumentEvidence,
    DocumentRecord,
    DocumentRevision,
    EvidenceKind,
    canonical_digest,
)

DEFINITION_ID = UUID("11111111-1111-4111-8111-111111111111")
RELEASE_ID = UUID("22222222-2222-4222-8222-222222222222")
RECORD_ID = UUID("33333333-3333-4333-8333-333333333333")
ACTOR_ID = UUID("44444444-4444-4444-8444-444444444444")
EVIDENCE_ID = UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime(2026, 9, 19, 10, tzinfo=UTC)


def definition() -> DocumentDefinition:
    payload = {"id": "kya:document-type:employee-satisfaction", "version": "1.0.0"}
    return DocumentDefinition(
        id=DEFINITION_ID,
        public_id="kya:document-type:employee-satisfaction",
        version="1.0.0",
        owner_scope="workspace:people",
        release_id=RELEASE_ID,
        definition=payload,
        digest=canonical_digest(payload),
        published_by=ACTOR_ID,
        published_at=NOW,
    )


def record(revision: int = 1) -> DocumentRecord:
    return DocumentRecord(
        id=RECORD_ID,
        definition_id=DEFINITION_ID,
        owner_scope="workspace:people",
        state="draft",
        current_revision=revision,
        created_by=ACTOR_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def revision(number: int = 1) -> DocumentRevision:
    payload = {"rating": number}
    return DocumentRevision(
        record_id=RECORD_ID,
        revision=number,
        payload=payload,
        digest=canonical_digest(payload),
        authored_by=ACTOR_ID,
        created_at=NOW,
    )


class Repository:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.current = record()
        self.latest = revision()
        self.evidence_rows: list[DocumentEvidence] = []

    async def publish_definition(self, value: DocumentDefinition) -> DocumentDefinition:
        return value

    async def get_definition(self, _public_id: str, _version: str) -> DocumentDefinition | None:
        return definition() if self.available else None

    async def create_record(
        self, value: DocumentRecord, initial: DocumentRevision
    ) -> DocumentRecord:
        self.current, self.latest = value, initial
        return value

    async def get_record(
        self, _record_id: UUID, *, owner_scope: str
    ) -> tuple[DocumentRecord, DocumentRevision] | None:
        if not self.available or owner_scope != self.current.owner_scope:
            return None
        return self.current, self.latest

    async def append_revision(
        self,
        value: DocumentRevision,
        *,
        owner_scope: str,
        expected_revision: int,
        state: str,
    ) -> DocumentRecord:
        assert owner_scope == self.current.owner_scope
        assert expected_revision == self.current.current_revision
        self.latest = value
        self.current = record(value.revision)
        return self.current

    async def append_evidence(
        self, value: DocumentEvidence, *, owner_scope: str
    ) -> DocumentEvidence:
        assert owner_scope == self.current.owner_scope
        self.evidence_rows.append(value)
        return value

    async def list_evidence(
        self, _record_id: UUID, *, owner_scope: str
    ) -> Sequence[DocumentEvidence]:
        return tuple(self.evidence_rows) if owner_scope == self.current.owner_scope else ()


@pytest.mark.asyncio
async def test_create_requires_published_definition() -> None:
    service = DocumentService(Repository(available=False))

    with pytest.raises(DocumentNotFoundError):
        await service.create(
            record=record(),
            revision=revision(),
            definition_public_id=definition().public_id,
            definition_version="1.0.0",
        )


@pytest.mark.asyncio
async def test_publish_create_revise_and_record_evidence() -> None:
    backend = Repository()
    service = DocumentService(backend)

    assert await service.publish_definition(definition()) == definition()
    assert (
        await service.create(
            record=record(),
            revision=revision(),
            definition_public_id=definition().public_id,
            definition_version="1.0.0",
        )
        == record()
    )
    assert (
        await service.revise(
            revision=revision(2),
            owner_scope="workspace:people",
            expected_revision=1,
            state="submitted",
        )
    ).current_revision == 2
    payload = {"from": "draft", "to": "submitted"}
    proof = DocumentEvidence(
        id=EVIDENCE_ID,
        record_id=RECORD_ID,
        revision=2,
        kind=EvidenceKind.TRANSITION,
        actor_id=ACTOR_ID,
        evidence=payload,
        digest=canonical_digest(payload),
        occurred_at=NOW,
    )
    assert await service.evidence(proof, owner_scope="workspace:people") == proof


@pytest.mark.asyncio
async def test_create_rejects_mismatched_initial_revision() -> None:
    service = DocumentService(Repository())

    with pytest.raises(DocumentConflictError, match="initial revision"):
        await service.create(
            record=record(),
            revision=revision(2),
            definition_public_id=definition().public_id,
            definition_version="1.0.0",
        )


@pytest.mark.asyncio
async def test_revision_must_follow_expected_revision() -> None:
    service = DocumentService(Repository())

    with pytest.raises(DocumentConflictError, match="immediately follow"):
        await service.revise(
            revision=revision(3),
            owner_scope="workspace:people",
            expected_revision=1,
            state="draft",
        )


@pytest.mark.asyncio
async def test_evidence_cannot_target_future_revision() -> None:
    service = DocumentService(Repository())
    payload = {"from": "draft", "to": "submitted"}
    evidence = DocumentEvidence(
        id=EVIDENCE_ID,
        record_id=RECORD_ID,
        revision=2,
        kind=EvidenceKind.TRANSITION,
        actor_id=ACTOR_ID,
        evidence=payload,
        digest=canonical_digest(payload),
        occurred_at=NOW,
    )

    with pytest.raises(DocumentConflictError, match="future"):
        await service.evidence(evidence, owner_scope="workspace:people")


@pytest.mark.asyncio
async def test_evidence_hides_record_outside_scope() -> None:
    service = DocumentService(Repository(available=False))

    with pytest.raises(DocumentNotFoundError):
        await service.evidence(
            DocumentEvidence(
                id=EVIDENCE_ID,
                record_id=RECORD_ID,
                revision=1,
                kind=EvidenceKind.SIGNATURE,
                actor_id=ACTOR_ID,
                evidence={"method": "approval"},
                digest=canonical_digest({"method": "approval"}),
                occurred_at=NOW,
            ),
            owner_scope="workspace:people",
        )
