"""A merged proposal is promoted once into a signed, workspace-scoped release."""

import base64
import json
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

import pytest

from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogPackageFile,
    CatalogRelease,
    OutboxEvent,
)
from kya_platform.infrastructure.database.proposal_publication import (
    SqlAlchemyMergedProposalPublisher,
)

PROPOSAL_ID = UUID("019914b2-1a40-7000-8000-0000000000c1")
WORKSPACE = UUID("019914b2-1a40-7000-8000-000000000071")
AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
BUSINESS = UUID("019914b2-1a40-7000-8000-000000000041")
TECHNICAL = UUID("019914b2-1a40-7000-8000-000000000042")
CORRELATION = UUID("019914b2-1a40-7000-8000-0000000000c2")
COMMIT = "a" * 40


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode()


def package() -> ProposalPackage:
    manifest = {
        "schemaVersion": "1",
        "id": "kya:skill:technical-brief",
        "type": "skill",
        "name": "Technical Brief",
        "version": "0.1.0",
        "summary": "A governed brief.",
        "owners": {"business": "communication", "technical": "cvsi", "workspace": "team"},
        "compatibility": {"claude-code": ">=2026-09", "codex": ">=2026-09"},
        "dependencies": [],
        "scopes": ["skill.discover"],
        "risk": "read",
    }
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                contentBase64=_encoded(json.dumps(manifest).encode()),
            ),
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                contentBase64=_encoded(b"---\nname: technical-brief\n---\n"),
            ),
        ]
    )


def proposal(**changes: object) -> Proposal:
    values: dict[str, object] = {
        "id": PROPOSAL_ID,
        "target_workspace_id": WORKSPACE,
        "slug": "technical-brief",
        "artifact_type": ArtifactType.SKILL,
        "artifact_id": None,
        "requested_by": AUTHOR,
        "requested_at": datetime(2026, 9, 18, tzinfo=UTC),
        "status": ProposalStatus.PULL_REQUEST_OPEN,
        "reviewer_id": REVIEWER,
        "reviewed_at": datetime(2026, 9, 18, tzinfo=UTC),
        "business_owner_id": BUSINESS,
        "technical_owner_id": TECHNICAL,
        "pull_request_url": "https://github.com/kya/platform/pull/1",
    }
    values.update(changes)
    return Proposal(**values)  # type: ignore[arg-type]


class Session:
    def __init__(self, scalars: list[object | None]) -> None:
        self.scalars = scalars
        self.added: list[object] = []

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    def begin(self) -> Session:
        return self

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalars.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


class Grants:
    def __init__(self) -> None:
        self.items: list[tuple[UUID, UUID]] = []

    async def grant_artifact_workspace(self, artifact_id: UUID, workspace_id: UUID) -> None:
        self.items.append((artifact_id, workspace_id))


def publisher(session: Session, grants: Grants) -> SqlAlchemyMergedProposalPublisher:
    signer = Ed25519ArtifactSigner.from_private_key_bytes("test-key", b"k" * 32)
    return SqlAlchemyMergedProposalPublisher(
        Sessions(session),  # type: ignore[arg-type]
        signer,
        grants,
        repository="kya/platform",
        public_api_url="https://api.kya.test",
    )


@pytest.mark.asyncio
async def test_publish_creates_signed_catalog_rows_and_grants_workspace() -> None:
    session = Session([None, None])
    grants = Grants()

    version_id = await publisher(session, grants).publish(
        proposal=proposal(), package=package(), commit_sha=COMMIT, correlation_id=CORRELATION
    )

    artifact = next(item for item in session.added if isinstance(item, CatalogArtifact))
    version = next(item for item in session.added if isinstance(item, CatalogArtifactVersion))
    release = next(item for item in session.added if isinstance(item, CatalogRelease))
    files = [item for item in session.added if isinstance(item, CatalogPackageFile)]
    event = next(item for item in session.added if isinstance(item, OutboxEvent))
    assert version_id == version.id
    assert artifact.lifecycle == "published"
    assert artifact.owner_workspace_id == WORKSPACE
    assert version.source_commit == COMMIT
    assert version.status == "published"
    assert {item.path for item in files} == {"SKILL.md", "artifact.manifest.json"}
    assert release.storage_locator.endswith("/releases/technical-brief/0.1.0/package")
    assert release.signature["key_id"] == "test-key"
    assert event.topic == "artifact.published"
    assert grants.items == [(artifact.id, WORKSPACE)]


@pytest.mark.asyncio
async def test_publish_is_idempotent_for_the_same_version() -> None:
    artifact = CatalogArtifact(
        id=UUID(int=10),
        registry_id="kya",
        slug="technical-brief",
        artifact_type="skill",
        name="Old name",
        owner_workspace_id=WORKSPACE,
        business_owner_id=BUSINESS,
        technical_owner_id=TECHNICAL,
        visibility="private",
        lifecycle="approved",
    )
    prepared = package()
    first_session = Session([None, None])
    first_grants = Grants()
    first_id = await publisher(first_session, first_grants).publish(
        proposal=proposal(), package=prepared, commit_sha=COMMIT, correlation_id=CORRELATION
    )
    created = next(
        item
        for item in first_session.added
        if isinstance(item, CatalogArtifactVersion) and item.id == first_id
    )
    artifact.id = created.artifact_id
    session = Session([artifact, created])
    grants = Grants()

    repeated_id = await publisher(session, grants).publish(
        proposal=proposal(artifact_id=artifact.id),
        package=prepared,
        commit_sha=COMMIT,
        correlation_id=CORRELATION,
    )

    assert repeated_id == created.id
    assert session.added == []
    assert artifact.name == "Technical Brief"
    assert grants.items == [(artifact.id, WORKSPACE)]


@pytest.mark.asyncio
async def test_publish_rejects_missing_review_owners() -> None:
    with pytest.raises(ValueError, match="owners"):
        await publisher(Session([]), Grants()).publish(
            proposal=proposal(business_owner_id=None),
            package=package(),
            commit_sha=COMMIT,
            correlation_id=CORRELATION,
        )


@pytest.mark.asyncio
async def test_publish_rejects_a_slug_owned_by_another_workspace() -> None:
    artifact = CatalogArtifact(
        id=UUID(int=10),
        registry_id="kya",
        slug="technical-brief",
        artifact_type="skill",
        name="Existing",
        owner_workspace_id=UUID(int=999),
        business_owner_id=BUSINESS,
        technical_owner_id=TECHNICAL,
        visibility="private",
        lifecycle="published",
    )
    with pytest.raises(ValueError, match="another workspace"):
        await publisher(Session([artifact]), Grants()).publish(
            proposal=proposal(), package=package(), commit_sha=COMMIT, correlation_id=CORRELATION
        )
