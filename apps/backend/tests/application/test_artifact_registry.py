"""Application tests for atomic artifact draft commands."""

from uuid import UUID

import pytest

from kya_platform.application.artifact_registry import (
    ArtifactDraft,
    ArtifactNotFoundError,
    ArtifactRecord,
    ArtifactRegistryService,
)
from kya_platform.contracts.artifact_package import ArtifactPackage

WORKSPACE = UUID("01991b00-0000-7000-8000-000000000001")
BUSINESS_OWNER = UUID("01991b00-0000-7000-8000-000000000002")
TECHNICAL_OWNER = UUID("01991b00-0000-7000-8000-000000000003")
ACTOR = UUID("01991b00-0000-7000-8000-000000000004")
CORRELATION = UUID("01991b00-0000-7000-8000-000000000005")


def package() -> ArtifactPackage:
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
                    "path": "skills/document-standard",
                },
                "integrity": {"algorithm": "sha256", "digest": "b" * 64},
                "compatibility": {"codex": ">=2026-09"},
                "scopes": ["skill.discover"],
                "risk": "read",
            },
            "files": [
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
            ],
        }
    )


class Registry:
    def __init__(self) -> None:
        self.created: ArtifactDraft | None = None
        self.record: ArtifactRecord | None = None

    async def create_draft(self, draft: ArtifactDraft) -> ArtifactRecord:
        self.created = draft
        self.record = ArtifactRecord(
            draft.artifact_id,
            draft.version_id,
            draft.workspace_id,
            "document-standard",
            "draft",
            "draft",
            draft.package,
        )
        return self.record

    async def get(self, artifact_id: UUID, workspace_id: UUID) -> ArtifactRecord | None:
        if self.record is None:
            return None
        if self.record.artifact_id != artifact_id or self.record.workspace_id != workspace_id:
            return None
        return self.record


@pytest.mark.asyncio
async def test_create_validates_identity_and_builds_a_complete_draft() -> None:
    repository = Registry()
    service = ArtifactRegistryService(repository)

    record = await service.create_draft(
        workspace_id=WORKSPACE,
        slug="document-standard",
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        package=package(),
        actor_id=ACTOR,
        correlation_id=CORRELATION,
    )

    assert record.slug == "document-standard"
    assert repository.created is not None
    assert len(repository.created.manifest_digest) == 64
    assert repository.created.created_by == ACTOR


@pytest.mark.asyncio
async def test_create_rejects_slug_manifest_mismatch_before_persistence() -> None:
    repository = Registry()

    with pytest.raises(ValueError, match="does not match"):
        await ArtifactRegistryService(repository).create_draft(
            workspace_id=WORKSPACE,
            slug="another-skill",
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            package=package(),
            actor_id=ACTOR,
            correlation_id=CORRELATION,
        )

    assert repository.created is None


@pytest.mark.asyncio
async def test_read_fails_closed_outside_the_scoped_workspace() -> None:
    repository = Registry()
    service = ArtifactRegistryService(repository)

    with pytest.raises(ArtifactNotFoundError):
        await service.get(UUID(int=10), WORKSPACE)
