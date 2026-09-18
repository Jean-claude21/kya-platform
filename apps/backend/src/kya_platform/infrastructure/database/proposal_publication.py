"""Idempotent promotion of a merged proposal into the governed catalog."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.artifact_registry.release_package import prepare_proposal_release
from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType, Proposal
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogCapabilityManifest,
    CatalogPackageFile,
    CatalogRelease,
    OutboxEvent,
)


class ArtifactWorkspaceGrant(Protocol):
    async def grant_artifact_workspace(self, artifact_id: UUID, workspace_id: UUID) -> None: ...


_SOURCE_DIRECTORIES = {
    ArtifactType.SKILL: "skills",
    ArtifactType.MCP_SERVER: "mcp-servers",
    ArtifactType.APPLICATION: "applications",
}


class SqlAlchemyMergedProposalPublisher:
    """Create one signed release from the exact package accepted by Studio and merged by GitHub."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        signer: Ed25519ArtifactSigner,
        grants: ArtifactWorkspaceGrant,
        *,
        repository: str,
        public_api_url: str,
    ) -> None:
        self._sessions = sessions
        self._signer = signer
        self._grants = grants
        self._repository = repository
        self._public_api_url = public_api_url.rstrip("/")

    async def publish(
        self,
        *,
        proposal: Proposal,
        package: ProposalPackage,
        commit_sha: str,
        correlation_id: UUID,
    ) -> UUID:
        if proposal.business_owner_id is None or proposal.technical_owner_id is None:
            raise ValueError("approved proposal owners are required for publication")
        try:
            source_directory = _SOURCE_DIRECTORIES[proposal.artifact_type]
        except KeyError as error:
            raise ValueError("proposal artifact type cannot be published") from error
        source_path = f"catalog/sources/{source_directory}/{proposal.slug}"
        source_repository = f"https://github.com/{self._repository}"
        prepared = prepare_proposal_release(
            proposal_package=package,
            slug=proposal.slug,
            artifact_type=proposal.artifact_type,
            source_repository=source_repository,
            source_commit=commit_sha,
            source_path=source_path,
        )
        manifest = prepared.package.artifact
        manifest_payload = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
        canonical_manifest = json.dumps(
            manifest_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            artifact = await session.scalar(
                select(CatalogArtifact)
                .where(
                    CatalogArtifact.registry_id == "kya",
                    CatalogArtifact.artifact_type == proposal.artifact_type.value,
                    CatalogArtifact.slug == proposal.slug,
                )
                .with_for_update()
            )
            if artifact is None:
                artifact = CatalogArtifact(
                    id=proposal.artifact_id or uuid7(),
                    registry_id="kya",
                    slug=proposal.slug,
                    artifact_type=proposal.artifact_type.value,
                    name=manifest.name,
                    summary=manifest.summary,
                    owner_workspace_id=proposal.target_workspace_id,
                    business_owner_id=proposal.business_owner_id,
                    technical_owner_id=proposal.technical_owner_id,
                    visibility="private",
                    lifecycle="published",
                    discoverable=False,
                )
                session.add(artifact)
            else:
                if proposal.artifact_id is not None and artifact.id != proposal.artifact_id:
                    raise ValueError("proposal artifact identity does not match the catalog")
                if artifact.owner_workspace_id != proposal.target_workspace_id:
                    raise ValueError("artifact slug already belongs to another workspace")
                artifact.name = manifest.name
                artifact.summary = manifest.summary
                artifact.business_owner_id = proposal.business_owner_id
                artifact.technical_owner_id = proposal.technical_owner_id
                artifact.lifecycle = "published"

            existing = await session.scalar(
                select(CatalogArtifactVersion).where(
                    CatalogArtifactVersion.artifact_id == artifact.id,
                    CatalogArtifactVersion.version == manifest.version,
                )
            )
            if existing is not None:
                if (
                    existing.source_commit != commit_sha.lower()
                    or existing.content_digest != manifest.integrity.digest.lower()
                ):
                    raise ValueError("artifact version already exists with different content")
                version_id = existing.id
            else:
                version_id = uuid7()
                version = CatalogArtifactVersion(
                    id=version_id,
                    artifact_id=artifact.id,
                    version=manifest.version,
                    status="published",
                    source_repository=source_repository,
                    source_commit=commit_sha.lower(),
                    source_path=source_path,
                    content_digest=manifest.integrity.digest.lower(),
                    manifest_digest=hashlib.sha256(canonical_manifest.encode()).hexdigest(),
                    manifest=manifest_payload,
                    inventory_digest=prepared.package.inventory_digest(),
                    package_size=sum(item.size for item in prepared.package.files),
                    file_count=len(prepared.package.files),
                    has_executable_content=prepared.package.has_executable_content,
                    risk=manifest.risk.value,
                    created_by=proposal.requested_by,
                )
                files = [
                    CatalogPackageFile(
                        version_id=version_id,
                        path=item.path,
                        media_type=item.media_type,
                        size=item.size,
                        sha256=item.sha256.lower(),
                        kind=item.kind.value,
                        executable=item.executable,
                    )
                    for item in prepared.package.files
                ]
                release_id = uuid7()
                signature = self._signer.sign(version_id, manifest.integrity.digest, signed_at=now)
                release = CatalogRelease(
                    id=release_id,
                    artifact_version_id=version_id,
                    content_digest=manifest.integrity.digest.lower(),
                    signature=signature.model_dump(mode="json"),
                    storage_locator=(
                        f"{self._public_api_url}/api/v1/releases/"
                        f"{proposal.slug}/{manifest.version}/package"
                    ),
                    status="published",
                    published_at=now,
                    published_by=proposal.reviewer_id or proposal.requested_by,
                )
                rows: list[object] = [version, *files, release]
                if prepared.package.capability is not None:
                    rows.append(
                        CatalogCapabilityManifest(
                            version_id=version_id,
                            schema_version=prepared.package.capability.schema_version,
                            runtime=prepared.package.capability.runtime,
                            declaration=prepared.package.capability.model_dump(
                                mode="json", by_alias=True, exclude_none=True
                            ),
                        )
                    )
                rows.append(
                    OutboxEvent(
                        topic="artifact.published",
                        aggregate_type="artifact_version",
                        aggregate_id=str(version_id),
                        correlation_id=correlation_id,
                        payload={
                            "artifact_id": str(artifact.id),
                            "proposal_id": str(proposal.id),
                            "release_id": str(release_id),
                            "version": manifest.version,
                            "content_digest": manifest.integrity.digest,
                            "archive_digest": prepared.archive_digest,
                        },
                    )
                )
                session.add_all(rows)

        await self._grants.grant_artifact_workspace(artifact.id, proposal.target_workspace_id)
        return version_id


__all__ = ["ArtifactWorkspaceGrant", "SqlAlchemyMergedProposalPublisher"]
