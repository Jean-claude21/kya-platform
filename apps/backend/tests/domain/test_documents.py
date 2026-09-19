"""Native document aggregates protect immutable content and evidence."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

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


def test_canonical_digest_is_independent_of_object_key_order() -> None:
    assert canonical_digest({"rating": 5, "comment": "Great"}) == canonical_digest(
        {"comment": "Great", "rating": 5}
    )


def test_definition_requires_digest_of_exact_canonical_content() -> None:
    payload = {"id": "kya:document-type:employee-satisfaction", "version": "1.0.0"}

    definition = DocumentDefinition(
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

    assert definition.definition == payload
    with pytest.raises(ValueError, match="digest"):
        DocumentDefinition(
            id=DEFINITION_ID,
            public_id=definition.public_id,
            version=definition.version,
            owner_scope=definition.owner_scope,
            release_id=definition.release_id,
            definition=payload,
            digest="0" * 64,
            published_by=ACTOR_ID,
            published_at=NOW,
        )


def test_record_revisions_and_evidence_are_bound_to_exact_content() -> None:
    payload = {"rating": 4, "comment": "Useful"}
    evidence_payload = {"from": "draft", "to": "submitted"}

    record = DocumentRecord(
        id=RECORD_ID,
        definition_id=DEFINITION_ID,
        owner_scope="workspace:people",
        state="submitted",
        current_revision=1,
        created_by=ACTOR_ID,
        created_at=NOW,
        updated_at=NOW,
    )
    revision = DocumentRevision(
        record_id=RECORD_ID,
        revision=1,
        payload=payload,
        digest=canonical_digest(payload),
        authored_by=ACTOR_ID,
        created_at=NOW,
    )
    evidence = DocumentEvidence(
        id=EVIDENCE_ID,
        record_id=RECORD_ID,
        revision=1,
        kind=EvidenceKind.TRANSITION,
        actor_id=ACTOR_ID,
        evidence=evidence_payload,
        digest=canonical_digest(evidence_payload),
        occurred_at=NOW,
    )

    assert record.current_revision == revision.revision == evidence.revision


@pytest.mark.parametrize("owner_scope", ["people", "unknown:people", "workspace:"])
def test_record_rejects_unmanaged_scopes(owner_scope: str) -> None:
    with pytest.raises(ValueError, match="owner_scope"):
        DocumentRecord(
            id=RECORD_ID,
            definition_id=DEFINITION_ID,
            owner_scope=owner_scope,
            state="draft",
            current_revision=1,
            created_by=ACTOR_ID,
            created_at=NOW,
            updated_at=NOW,
        )


def test_document_values_reject_binary_or_runtime_objects() -> None:
    with pytest.raises(ValueError, match="JSON compatible"):
        canonical_digest({"attachment": b"secret"})  # type: ignore[dict-item]
