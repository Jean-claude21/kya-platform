"""The catalog adapter persists and reconstructs complete packages atomically."""

from typing import Self
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from kya_platform.application.artifact_registry import ArtifactConflictError, ArtifactDraft
from kya_platform.contracts.artifact_package import ArtifactPackage
from kya_platform.infrastructure.database.artifact_registry import SqlAlchemyArtifactRegistry
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogCapabilityManifest,
    CatalogPackageFile,
    OutboxEvent,
)

WORKSPACE = UUID("01991b00-0000-7000-8000-000000000001")
OWNER = UUID("01991b00-0000-7000-8000-000000000002")
ACTOR = UUID("01991b00-0000-7000-8000-000000000003")
ARTIFACT = UUID("01991b00-0000-7000-8000-000000000004")
VERSION = UUID("01991b00-0000-7000-8000-000000000005")
CORRELATION = UUID("01991b00-0000-7000-8000-000000000006")


def package(*, executable: bool = False) -> ArtifactPackage:
    files: list[dict[str, object]] = [
        {
            "path": "artifact.manifest.json",
            "mediaType": "application/json",
            "size": 600,
            "sha256": "c" * 64,
            "kind": "manifest",
        },
        {
            "path": "SKILL.md",
            "mediaType": "text/markdown",
            "size": 900,
            "sha256": "d" * 64,
            "kind": "instruction",
        },
    ]
    capability = None
    if executable:
        files.extend(
            [
                {
                    "path": "capability.manifest.json",
                    "mediaType": "application/json",
                    "size": 300,
                    "sha256": "e" * 64,
                    "kind": "manifest",
                },
                {
                    "path": "scripts/render.py",
                    "mediaType": "text/x-python",
                    "size": 400,
                    "sha256": "f" * 64,
                    "kind": "script",
                    "executable": True,
                },
            ]
        )
        capability = {
            "schemaVersion": "1",
            "runtime": "python>=3.14",
            "entrypoints": {"render": "scripts/render.py"},
            "secretReferences": ["infisical://skills/document-standard/api-key"],
            "requestedPermissions": ["document.render"],
        }
    return ArtifactPackage.model_validate(
        {
            "schemaVersion": "1",
            "artifact": {
                "schemaVersion": "1",
                "id": "kya:skill:document-standard",
                "type": "skill",
                "name": "Standard documentaire KYA",
                "version": "1.0.0",
                "owners": {
                    "business": "communication",
                    "technical": "cvsi-platform",
                    "workspace": "communication",
                },
                "source": {
                    "repository": "https://github.com/kya-energy/document-standard",
                    "commit": "a" * 40,
                },
                "integrity": {"algorithm": "sha256", "digest": "b" * 64},
                "compatibility": {"codex": ">=2026-09"},
            },
            "files": files,
            "capability": capability,
        }
    )


def draft(*, executable: bool = False) -> ArtifactDraft:
    return ArtifactDraft(
        artifact_id=ARTIFACT,
        version_id=VERSION,
        workspace_id=WORKSPACE,
        business_owner_id=OWNER,
        technical_owner_id=OWNER,
        package=package(executable=executable),
        manifest_digest="1" * 64,
        created_by=ACTOR,
        correlation_id=CORRELATION,
    )


class Result:
    def __init__(self, *, first: object = None, scalars: list[object] | None = None) -> None:
        self._first = first
        self._scalars = scalars or []

    def first(self) -> object:
        return self._first

    def scalars(self) -> Result:
        return self

    def all(self) -> list[object]:
        return self._scalars

    def scalar_one_or_none(self) -> object:
        return self._first


class Session:
    def __init__(self, results: list[Result] | None = None, *, fail_add: bool = False) -> None:
        self.results = results or []
        self.fail_add = fail_add
        self.rows: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> Session:
        return self

    def add_all(self, rows: list[object]) -> None:
        if self.fail_add:
            raise IntegrityError("insert", {}, RuntimeError("duplicate"))
        self.rows.extend(rows)

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def execute(self, statement: object) -> Result:
        del statement
        return self.results.pop(0)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_create_persists_package_capability_and_outbox_together() -> None:
    session = Session()
    repository = SqlAlchemyArtifactRegistry(Sessions(session))  # type: ignore[arg-type]

    record = await repository.create_draft(draft(executable=True))

    assert record.package.has_executable_content is True
    assert any(isinstance(row, CatalogArtifact) for row in session.rows)
    assert any(isinstance(row, CatalogArtifactVersion) for row in session.rows)
    assert len([row for row in session.rows if isinstance(row, CatalogPackageFile)]) == 4
    assert any(isinstance(row, CatalogCapabilityManifest) for row in session.rows)
    event = next(row for row in session.rows if isinstance(row, OutboxEvent))
    assert event.correlation_id == CORRELATION
    assert "secret" not in event.payload


@pytest.mark.asyncio
async def test_create_converts_database_uniqueness_failure_to_domain_conflict() -> None:
    repository = SqlAlchemyArtifactRegistry(Sessions(Session(fail_add=True)))  # type: ignore[arg-type]

    with pytest.raises(ArtifactConflictError):
        await repository.create_draft(draft())


@pytest.mark.asyncio
async def test_get_reconstructs_the_complete_validated_package() -> None:
    original = package(executable=True)
    artifact = CatalogArtifact(
        id=ARTIFACT,
        registry_id="kya",
        slug="document-standard",
        artifact_type="skill",
        name="Standard documentaire KYA",
        owner_workspace_id=WORKSPACE,
        business_owner_id=OWNER,
        technical_owner_id=OWNER,
        lifecycle="draft",
        visibility="private",
    )
    version = CatalogArtifactVersion(
        id=VERSION,
        artifact_id=ARTIFACT,
        version="1.0.0",
        status="draft",
        source_repository="https://github.com/kya-energy/document-standard",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="1" * 64,
        manifest=original.artifact.model_dump(mode="json", by_alias=True, exclude_none=True),
        inventory_digest=original.inventory_digest(),
        package_size=sum(item.size for item in original.files),
        file_count=len(original.files),
        has_executable_content=True,
        risk="read",
        created_by=ACTOR,
    )
    file_rows = [
        CatalogPackageFile(
            version_id=VERSION,
            path=item.path,
            media_type=item.media_type,
            size=item.size,
            sha256=item.sha256,
            kind=item.kind.value,
            executable=item.executable,
        )
        for item in original.files
    ]
    assert original.capability is not None
    capability = CatalogCapabilityManifest(
        version_id=VERSION,
        schema_version="1",
        runtime=original.capability.runtime,
        declaration=original.capability.model_dump(mode="json", by_alias=True),
    )
    session = Session(
        [Result(first=(artifact, version)), Result(scalars=file_rows), Result(first=capability)]
    )
    repository = SqlAlchemyArtifactRegistry(Sessions(session))  # type: ignore[arg-type]

    record = await repository.get(ARTIFACT, WORKSPACE)

    assert record is not None
    assert record.package.inventory_digest() == original.inventory_digest()
    assert record.package.capability is not None


@pytest.mark.asyncio
async def test_get_returns_none_without_disclosing_an_unknown_artifact() -> None:
    repository = SqlAlchemyArtifactRegistry(  # type: ignore[arg-type]
        Sessions(Session([Result(first=None)]))
    )

    assert await repository.get(ARTIFACT, WORKSPACE) is None
