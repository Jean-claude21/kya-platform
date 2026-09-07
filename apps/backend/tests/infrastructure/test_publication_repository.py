"""Neon publication adapter keeps workflow, release and outbox atomic."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application import OutboxMessage
from kya_platform.application.publication.evidence import AttestationKind
from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.domain.catalog import (
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    PublicationStatus,
    ReviewDecision,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogAttestation,
    CatalogPublicationRequest,
    CatalogRelease,
    OutboxEvent,
)
from kya_platform.infrastructure.database.publication import (
    SqlAlchemyOutbox,
    SqlAlchemyPublicationRepository,
    SqlAlchemyPublicationUnitOfWork,
)

ARTIFACT_ID = UUID("01991b00-0000-7000-8000-000000000101")
VERSION_ID = UUID("01991b00-0000-7000-8000-000000000102")
REQUEST_ID = UUID("01991b00-0000-7000-8000-000000000103")
AUTHOR = UUID("01991b00-0000-7000-8000-000000000104")
REVIEWER = UUID("01991b00-0000-7000-8000-000000000105")
APPROVER = UUID("01991b00-0000-7000-8000-000000000106")
CORRELATION = UUID("01991b00-0000-7000-8000-000000000107")
NOW = datetime(2026, 9, 7, 5, 0, tzinfo=UTC)
EVIDENCE_IDS = tuple(UUID(int=300 + index) for index in range(5))
EVIDENCE_KINDS = (
    AttestationKind.PROVENANCE,
    AttestationKind.SECRET_SCAN,
    AttestationKind.LICENSE,
    AttestationKind.COMPATIBILITY,
    AttestationKind.BUSINESS_VALIDATION,
)


def candidate() -> ArtifactVersion:
    return ArtifactVersion(ARTIFACT_ID, "1.0.0", "a" * 40, "b" * 64, "c" * 64)


def open_request() -> PublicationRequest:
    return PublicationRequest.open(
        id=REQUEST_ID,
        candidate=candidate(),
        requested_by=AUTHOR,
        requested_at=NOW,
        separation_of_duties=True,
        evidence_ids=EVIDENCE_IDS,
    )


def version_row() -> CatalogArtifactVersion:
    return CatalogArtifactVersion(
        id=VERSION_ID,
        artifact_id=ARTIFACT_ID,
        version="1.0.0",
        status="approved",
        source_repository="https://github.com/kya-energy/skill",
        source_commit="a" * 40,
        source_path="skills/one",
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={},
        inventory_digest="d" * 64,
        package_size=10,
        file_count=1,
        has_executable_content=False,
        risk="read",
        created_by=AUTHOR,
    )


def artifact_row() -> CatalogArtifact:
    return CatalogArtifact(
        id=ARTIFACT_ID,
        registry_id="kya",
        slug="one",
        artifact_type="skill",
        name="One",
        owner_workspace_id=UUID(int=1),
        business_owner_id=UUID(int=2),
        technical_owner_id=UUID(int=3),
        visibility="private",
        lifecycle="approved",
    )


def request_row() -> CatalogPublicationRequest:
    return CatalogPublicationRequest(
        id=REQUEST_ID,
        artifact_id=ARTIFACT_ID,
        artifact_version_id=VERSION_ID,
        version="1.0.0",
        commit_sha="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        requested_by=AUTHOR,
        requested_at=NOW,
        separation_of_duties=True,
        evidence_ids=[str(item) for item in EVIDENCE_IDS],
        status="awaiting-review",
        revision=1,
    )


class Session:
    def __init__(self, scalars: list[object | None] | None = None) -> None:
        self.scalars = scalars or []
        self.gets: dict[tuple[type[object], UUID], object] = {}
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self.active = False

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalars.pop(0)

    async def get(self, model: type[object], identifier: UUID) -> object | None:
        return self.gets.get((model, identifier))

    def add(self, row: object) -> None:
        self.added.append(row)

    async def begin(self) -> None:
        self.active = True

    def in_transaction(self) -> bool:
        return self.active

    async def commit(self) -> None:
        self.commits += 1
        self.active = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.active = False

    async def close(self) -> None:
        self.closed += 1


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def signer() -> Ed25519ArtifactSigner:
    return Ed25519ArtifactSigner.from_private_key_bytes("kya-dev-2026", b"k" * 32)


def add_evidence(session: Session) -> None:
    for evidence_id, kind in zip(EVIDENCE_IDS, EVIDENCE_KINDS, strict=True):
        session.gets[(CatalogAttestation, evidence_id)] = CatalogAttestation(
            id=evidence_id,
            artifact_version_id=VERSION_ID,
            kind=kind.value,
            predicate_type=f"https://schemas.kya.energy/attestation/{kind.value}/v1",
            digest="e" * 64,
            issuer_id=REVIEWER,
            subject_digest="b" * 64,
            result="passed",
            valid_from=NOW,
            valid_until=None,
            evidence_uri=f"https://evidence.kya.energy/{kind.value}/1",
        )


@pytest.mark.asyncio
async def test_insert_requires_an_exact_persisted_candidate() -> None:
    session = Session([None, version_row()])
    add_evidence(session)
    repository = SqlAlchemyPublicationRepository(session, signer())  # type: ignore[arg-type]

    await repository.save(open_request())

    row = next(item for item in session.added if isinstance(item, CatalogPublicationRequest))
    assert row.artifact_version_id == VERSION_ID
    assert row.status == "awaiting-review"


@pytest.mark.asyncio
async def test_insert_rejects_candidate_not_found_in_neon() -> None:
    repository = SqlAlchemyPublicationRepository(Session([None, None]), signer())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="persisted artifact version"):
        await repository.save(open_request())


@pytest.mark.asyncio
async def test_insert_rejects_incomplete_evidence() -> None:
    session = Session([None, version_row()])
    add_evidence(session)
    del session.gets[(CatalogAttestation, EVIDENCE_IDS[-1])]
    repository = SqlAlchemyPublicationRepository(session, signer())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="does not belong"):
        await repository.save(open_request())


@pytest.mark.asyncio
async def test_publishing_creates_a_signed_immutable_release() -> None:
    row = request_row()
    version = version_row()
    artifact = artifact_row()
    session = Session([row])
    session.gets[(CatalogArtifactVersion, VERSION_ID)] = version
    session.gets[(CatalogArtifact, ARTIFACT_ID)] = artifact
    repository = SqlAlchemyPublicationRepository(session, signer())  # type: ignore[arg-type]
    published = (
        open_request()
        .review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        .approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
        .mark_published(APPROVER, content_digest="b" * 64, at=NOW)
    )

    await repository.save(published)

    release = next(item for item in session.added if isinstance(item, CatalogRelease))
    assert release.content_digest == "b" * 64
    assert release.signature["key_id"] == "kya-dev-2026"
    assert release.storage_locator.endswith("@" + "a" * 40 + "#skills/one")
    assert version.status == "published"
    assert artifact.lifecycle == "published"
    assert row.revision == 2


@pytest.mark.asyncio
async def test_get_reconstructs_review_and_approval_evidence() -> None:
    row = request_row()
    row.status = "approved"
    row.reviewer_id = REVIEWER
    row.review_decision = "accepted"
    row.reviewed_at = NOW
    row.approver_id = APPROVER
    row.approval_decision = "approved"
    row.approved_at = NOW
    repository = SqlAlchemyPublicationRepository(Session([row]), signer())  # type: ignore[arg-type]

    restored = await repository.get(REQUEST_ID)

    assert restored is not None
    assert restored.status is PublicationStatus.APPROVED
    assert restored.review_record is not None
    assert restored.approval is not None


@pytest.mark.asyncio
async def test_outbox_and_unit_of_work_share_the_same_transaction() -> None:
    session = Session()
    outbox = SqlAlchemyOutbox(session)  # type: ignore[arg-type]
    await outbox.add(
        OutboxMessage("artifact.published", "artifact", str(ARTIFACT_ID), {}, CORRELATION)
    )
    assert isinstance(session.added[0], OutboxEvent)

    unit = SqlAlchemyPublicationUnitOfWork(Sessions(session), signer())  # type: ignore[arg-type]
    async with unit:
        await unit.commit()

    assert session.commits == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_when_left_without_commit() -> None:
    session = Session()
    unit = SqlAlchemyPublicationUnitOfWork(Sessions(session), signer())  # type: ignore[arg-type]

    async with unit:
        pass

    assert session.rollbacks == 1
    assert session.closed == 1


@pytest.mark.asyncio
async def test_unit_of_work_rejects_commit_before_entry() -> None:
    unit = SqlAlchemyPublicationUnitOfWork(Sessions(Session()), signer())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="not active"):
        await unit.commit()
