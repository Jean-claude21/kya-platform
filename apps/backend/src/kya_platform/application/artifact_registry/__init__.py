"""Creation and scoped retrieval of validated catalog packages."""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid7

from kya_platform.contracts.artifact_package import ArtifactPackage
from kya_platform.domain.catalog import Artifact, ArtifactType


class ArtifactConflictError(ValueError):
    """The stable identifier or candidate version already exists."""


class ArtifactNotFoundError(LookupError):
    """The artifact is absent from the already-authorized workspace."""


@dataclass(frozen=True, slots=True)
class ArtifactDraft:
    artifact_id: UUID
    version_id: UUID
    workspace_id: UUID
    business_owner_id: UUID
    technical_owner_id: UUID
    package: ArtifactPackage
    manifest_digest: str
    created_by: UUID
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: UUID
    version_id: UUID
    workspace_id: UUID
    slug: str
    lifecycle: str
    status: str
    package: ArtifactPackage


class ArtifactRegistryPort(Protocol):
    async def create_draft(self, draft: ArtifactDraft) -> ArtifactRecord: ...

    async def get(self, artifact_id: UUID, workspace_id: UUID) -> ArtifactRecord | None: ...


class ArtifactRegistryService:
    def __init__(self, repository: ArtifactRegistryPort) -> None:
        self._repository = repository

    async def create_draft(
        self,
        *,
        workspace_id: UUID,
        slug: str,
        business_owner_id: UUID,
        technical_owner_id: UUID,
        package: ArtifactPackage,
        actor_id: UUID,
        correlation_id: UUID,
    ) -> ArtifactRecord:
        expected_id = f"kya:{package.artifact.artifact_type.value}:{slug}"
        if package.artifact.artifact_id != expected_id:
            raise ValueError("artifact manifest id does not match its type and slug")
        Artifact(
            id=UUID(int=0),
            slug=slug,
            artifact_type=ArtifactType(package.artifact.artifact_type.value),
            name=package.artifact.name,
            owner_workspace_id=workspace_id,
            business_owner_id=business_owner_id,
            technical_owner_id=technical_owner_id,
        )
        manifest_payload = package.artifact.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        canonical_manifest = json.dumps(
            manifest_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        draft = ArtifactDraft(
            artifact_id=uuid7(),
            version_id=uuid7(),
            workspace_id=workspace_id,
            business_owner_id=business_owner_id,
            technical_owner_id=technical_owner_id,
            package=package,
            manifest_digest=hashlib.sha256(canonical_manifest.encode()).hexdigest(),
            created_by=actor_id,
            correlation_id=correlation_id,
        )
        return await self._repository.create_draft(draft)

    async def get(self, artifact_id: UUID, workspace_id: UUID) -> ArtifactRecord:
        record = await self._repository.get(artifact_id, workspace_id)
        if record is None:
            raise ArtifactNotFoundError("artifact not found")
        return record


__all__ = [
    "ArtifactConflictError",
    "ArtifactDraft",
    "ArtifactNotFoundError",
    "ArtifactRecord",
    "ArtifactRegistryPort",
    "ArtifactRegistryService",
]
