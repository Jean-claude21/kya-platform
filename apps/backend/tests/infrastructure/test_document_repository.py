"""Document persistence keeps definitions, revisions and evidence immutable."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from kya_platform.application.documents import DocumentConflictError, DocumentNotFoundError
from kya_platform.application.documents.runtime import NotificationIntent, TransitionPlan
from kya_platform.contracts.document_type import ActorSelector, ActorSelectorKind
from kya_platform.domain.documents import (
    DocumentDefinition,
    DocumentEvidence,
    DocumentRecord,
    DocumentRevision,
    EvidenceKind,
    canonical_digest,
)
from kya_platform.infrastructure.database.documents import SqlAlchemyDocumentRepository

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


def record(*, revision: int = 1) -> DocumentRecord:
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


def evidence() -> DocumentEvidence:
    payload = {"from": "draft", "to": "submitted"}
    return DocumentEvidence(
        id=EVIDENCE_ID,
        record_id=RECORD_ID,
        revision=1,
        kind=EvidenceKind.TRANSITION,
        actor_id=ACTOR_ID,
        evidence=payload,
        digest=canonical_digest(payload),
        occurred_at=NOW,
    )


def transition_plan() -> TransitionPlan:
    next_revision = revision(2)
    proof_payload = {
        "transitionKey": "submit",
        "fromState": "draft",
        "toState": "submitted",
        "revisionDigest": next_revision.digest,
    }
    return TransitionPlan(
        transition_key="submit",
        from_state="draft",
        to_state="submitted",
        revision=next_revision,
        evidence=DocumentEvidence(
            id=EVIDENCE_ID,
            record_id=RECORD_ID,
            revision=2,
            kind=EvidenceKind.TRANSITION,
            actor_id=ACTOR_ID,
            evidence=proof_payload,
            digest=canonical_digest(proof_payload),
            occurred_at=NOW,
        ),
        notifications=(
            NotificationIntent(
                policy_key="mission_submitted",
                event="document.submitted",
                recipients=(ActorSelector(kind=ActorSelectorKind.ROLE, value="manager"),),
                channels=("in-app", "email"),
                template="operations.mission.submitted",
                available_at=NOW,
            ),
        ),
    )


def definition_row() -> SimpleNamespace:
    value = definition()
    return (
        SimpleNamespace(**value.__dict__)
        if hasattr(value, "__dict__")
        else SimpleNamespace(
            id=value.id,
            public_id=value.public_id,
            version=value.version,
            owner_scope=value.owner_scope,
            release_id=value.release_id,
            definition=dict(value.definition),
            digest=value.digest,
            published_by=value.published_by,
            published_at=value.published_at,
        )
    )


def record_row(*, current_revision: int = 1) -> SimpleNamespace:
    value = record(revision=current_revision)
    return SimpleNamespace(
        id=value.id,
        definition_id=value.definition_id,
        owner_scope=value.owner_scope,
        state=value.state,
        current_revision=value.current_revision,
        created_by=value.created_by,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def revision_row(number: int = 1) -> SimpleNamespace:
    value = revision(number)
    return SimpleNamespace(
        record_id=value.record_id,
        revision=value.revision,
        payload=dict(value.payload),
        digest=value.digest,
        authored_by=value.authored_by,
        created_at=value.created_at,
    )


def evidence_row() -> SimpleNamespace:
    value = evidence()
    return SimpleNamespace(
        id=value.id,
        record_id=value.record_id,
        revision=value.revision,
        kind=value.kind.value,
        actor_id=value.actor_id,
        evidence=dict(value.evidence),
        digest=value.digest,
        occurred_at=value.occurred_at,
    )


class Session:
    def __init__(
        self,
        *,
        scalars: list[object | None] | None = None,
        gets: list[object | None] | None = None,
        scalar_lists: list[tuple[object, ...]] | None = None,
    ) -> None:
        self.scalar_values = list(scalars or [])
        self.get_values = list(gets or [])
        self.scalar_lists = list(scalar_lists or [])
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def scalar(self, _statement: object) -> object | None:
        return self.scalar_values.pop(0)

    async def get(self, _model: object, _identifier: object) -> object | None:
        return self.get_values.pop(0)

    async def scalars(self, _statement: object) -> tuple[object, ...]:
        return self.scalar_lists.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def repository(session: Session) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(Sessions(session))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_publish_and_read_definition() -> None:
    insert = Session(scalars=[None])
    assert await repository(insert).publish_definition(definition()) == definition()
    assert len(insert.added) == 1 and insert.commits == 1

    existing = definition_row()
    assert (
        await repository(Session(scalars=[existing])).publish_definition(definition())
        == definition()
    )
    assert (
        await repository(Session(scalars=[existing])).get_definition(
            definition().public_id, "1.0.0"
        )
        == definition()
    )
    assert (
        await repository(Session(scalars=[None])).get_definition(definition().public_id, "9.0.0")
        is None
    )


@pytest.mark.asyncio
async def test_publish_rejects_reused_identity_with_different_release() -> None:
    existing = definition_row()
    existing.release_id = UUID("99999999-9999-4999-8999-999999999999")
    with pytest.raises(DocumentConflictError, match="different immutable content"):
        await repository(Session(scalars=[existing])).publish_definition(definition())


@pytest.mark.asyncio
async def test_create_and_get_record_with_current_revision() -> None:
    insert = Session(gets=[definition_row()])
    assert await repository(insert).create_record(record(), revision()) == record()
    assert len(insert.added) == 2 and insert.commits == 1

    found = await repository(Session(scalars=[record_row()], gets=[revision_row()])).get_record(
        RECORD_ID, owner_scope="workspace:people"
    )
    assert found == (record(), revision())
    assert (
        await repository(Session(scalars=[None])).get_record(
            RECORD_ID, owner_scope="workspace:other"
        )
        is None
    )


@pytest.mark.asyncio
async def test_create_rejects_missing_definition_or_scope_mismatch() -> None:
    with pytest.raises(DocumentNotFoundError):
        await repository(Session(gets=[None])).create_record(record(), revision())

    mismatched = definition_row()
    mismatched.owner_scope = "workspace:other"
    with pytest.raises(DocumentConflictError, match="scope"):
        await repository(Session(gets=[mismatched])).create_record(record(), revision())


@pytest.mark.asyncio
async def test_append_revision_uses_optimistic_lock_and_updates_head() -> None:
    row = record_row()
    updated = await repository(Session(scalars=[row])).append_revision(
        revision(2),
        owner_scope="workspace:people",
        expected_revision=1,
        state="submitted",
    )
    assert updated.current_revision == 2
    assert updated.state == "submitted"

    with pytest.raises(DocumentConflictError, match="concurrently"):
        await repository(Session(scalars=[record_row(current_revision=2)])).append_revision(
            revision(2),
            owner_scope="workspace:people",
            expected_revision=1,
            state="submitted",
        )

    with pytest.raises(DocumentNotFoundError):
        await repository(Session(scalars=[None])).append_revision(
            revision(2),
            owner_scope="workspace:people",
            expected_revision=1,
            state="submitted",
        )


@pytest.mark.asyncio
async def test_get_record_detects_broken_revision_pointer() -> None:
    with pytest.raises(RuntimeError, match="current revision"):
        await repository(Session(scalars=[record_row()], gets=[None])).get_record(
            RECORD_ID, owner_scope="workspace:people"
        )


@pytest.mark.asyncio
async def test_transition_commits_revision_evidence_and_outbox_atomically() -> None:
    row = record_row()
    session = Session(scalars=[row])

    updated = await repository(session).commit_transition(
        transition_plan(),
        owner_scope="workspace:people",
        correlation_id=UUID("66666666-6666-4666-8666-666666666666"),
    )

    assert updated.state == "submitted"
    assert updated.current_revision == 2
    assert session.commits == 1
    assert len(session.added) == 4
    topics = {getattr(item, "topic", None) for item in session.added}
    assert topics == {None, "document.transitioned", "document.notification.requested"}
    notification = next(
        item
        for item in session.added
        if getattr(item, "topic", None) == "document.notification.requested"
    )
    assert notification.payload["recipients"] == [{"kind": "role", "value": "manager"}]


@pytest.mark.asyncio
async def test_transition_fails_if_record_moved_or_is_outside_scope() -> None:
    with pytest.raises(DocumentNotFoundError):
        await repository(Session(scalars=[None])).commit_transition(
            transition_plan(),
            owner_scope="workspace:other",
            correlation_id=UUID("66666666-6666-4666-8666-666666666666"),
        )

    moved = record_row(current_revision=2)
    moved.state = "submitted"
    with pytest.raises(DocumentConflictError, match="changed"):
        await repository(Session(scalars=[moved])).commit_transition(
            transition_plan(),
            owner_scope="workspace:people",
            correlation_id=UUID("66666666-6666-4666-8666-666666666666"),
        )


@pytest.mark.asyncio
async def test_append_and_list_evidence_are_scope_filtered() -> None:
    value = evidence()
    inserted = Session(scalars=[record_row()])
    assert (
        await repository(inserted).append_evidence(value, owner_scope="workspace:people") == value
    )
    assert len(inserted.added) == 1

    listed = await repository(
        Session(scalars=[RECORD_ID], scalar_lists=[(evidence_row(),)])
    ).list_evidence(RECORD_ID, owner_scope="workspace:people")
    assert listed == (value,)
    assert (
        await repository(Session(scalars=[None])).list_evidence(
            RECORD_ID, owner_scope="workspace:other"
        )
        == ()
    )


@pytest.mark.asyncio
async def test_evidence_rejects_absent_record_and_future_revision() -> None:
    with pytest.raises(DocumentNotFoundError):
        await repository(Session(scalars=[None])).append_evidence(
            evidence(), owner_scope="workspace:people"
        )

    future = evidence()
    object.__setattr__(future, "revision", 2)
    with pytest.raises(DocumentConflictError, match="future"):
        await repository(Session(scalars=[record_row()])).append_evidence(
            future, owner_scope="workspace:people"
        )
