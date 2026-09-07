"""Digest-bound publication attestations are persisted atomically."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from kya_platform.application.publication.evidence import (
    AttestationKind,
    required_attestation_kinds,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifactVersion,
    CatalogAttestation,
    OutboxEvent,
)
from kya_platform.infrastructure.database.publication import SqlAlchemyAttestationRepository

ARTIFACT_ID = UUID("01991b00-0000-7000-8000-000000000201")
VERSION_ID = UUID("01991b00-0000-7000-8000-000000000202")
ISSUER_ID = UUID("01991b00-0000-7000-8000-000000000203")
CORRELATION_ID = UUID("01991b00-0000-7000-8000-000000000204")
NOW = datetime(2026, 9, 7, 6, 0, tzinfo=UTC)


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
        created_by=ISSUER_ID,
    )


class AttestationSession:
    def __init__(self, version: CatalogArtifactVersion | None) -> None:
        self.version = version
        self.added: list[object] = []
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> AttestationSession:
        self.entered += 1
        return self

    async def __aexit__(self, *args: object) -> None:
        del args
        self.exited += 1

    def begin(self) -> AttestationSession:
        return self

    async def scalar(self, statement: object) -> CatalogArtifactVersion | None:
        del statement
        return self.version

    def add(self, row: object) -> None:
        self.added.append(row)


class Sessions:
    def __init__(self, session: AttestationSession) -> None:
        self.session = session

    def __call__(self) -> AttestationSession:
        return self.session


def repository(session: AttestationSession) -> SqlAlchemyAttestationRepository:
    return SqlAlchemyAttestationRepository(Sessions(session))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_binds_evidence_to_version_digest_and_emits_outbox() -> None:
    session = AttestationSession(version_row())

    record = await repository(session).create(
        artifact_id=ARTIFACT_ID,
        version_id=VERSION_ID,
        kind=AttestationKind.PROVENANCE,
        issuer_id=ISSUER_ID,
        result="passed",
        valid_from=NOW,
        valid_until=NOW + timedelta(days=30),
        evidence_uri="https://evidence.kya.energy/provenance/1",
        correlation_id=CORRELATION_ID,
    )

    row = next(item for item in session.added if isinstance(item, CatalogAttestation))
    event = next(item for item in session.added if isinstance(item, OutboxEvent))
    assert record.id == row.id
    assert record.subject_digest == "b" * 64
    assert len(row.digest) == 64
    assert event.topic == "artifact.attestation.recorded"
    assert event.correlation_id == CORRELATION_ID
    assert session.entered == 2
    assert session.exited == 2


@pytest.mark.asyncio
async def test_create_rejects_unknown_version_without_writing() -> None:
    session = AttestationSession(None)

    with pytest.raises(ValueError, match="does not exist"):
        await repository(session).create(
            artifact_id=ARTIFACT_ID,
            version_id=VERSION_ID,
            kind=AttestationKind.PROVENANCE,
            issuer_id=ISSUER_ID,
            result="passed",
            valid_from=NOW,
            valid_until=None,
            evidence_uri="https://evidence.kya.energy/provenance/1",
            correlation_id=CORRELATION_ID,
        )

    assert session.added == []


@pytest.mark.asyncio
async def test_create_rejects_invalid_result_and_validity_window() -> None:
    session = AttestationSession(version_row())
    common = {
        "artifact_id": ARTIFACT_ID,
        "version_id": VERSION_ID,
        "kind": AttestationKind.PROVENANCE,
        "issuer_id": ISSUER_ID,
        "valid_from": NOW,
        "evidence_uri": "https://evidence.kya.energy/provenance/1",
        "correlation_id": CORRELATION_ID,
    }

    with pytest.raises(ValueError, match="result"):
        await repository(session).create(result="unknown", valid_until=None, **common)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="expiration"):
        await repository(session).create(
            result="passed",
            valid_until=NOW - timedelta(seconds=1),
            **common,  # type: ignore[arg-type]
        )

    assert session.added == []


def test_executable_or_mutating_artifacts_require_extended_evidence() -> None:
    minimal = required_attestation_kinds(risk="read", has_executable_content=False)
    executable = required_attestation_kinds(risk="read", has_executable_content=True)
    mutating = required_attestation_kinds(risk="write", has_executable_content=False)

    assert len(minimal) == 5
    assert {
        AttestationKind.TESTS,
        AttestationKind.DEPENDENCY_SCAN,
        AttestationKind.SBOM,
        AttestationKind.SECURITY,
    }.issubset(executable)
    assert executable == mutating
