"""Transactional Neon adapter for the governed artifact registry."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.artifact_registry import (
    ArtifactConflictError,
    ArtifactDraft,
    ArtifactRecord,
)
from kya_platform.contracts.artifact_package import ArtifactPackage
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogCapabilityManifest,
    CatalogPackageFile,
    OutboxEvent,
)


class SqlAlchemyArtifactRegistry:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create_draft(self, draft: ArtifactDraft) -> ArtifactRecord:
        package = draft.package
        manifest = package.artifact
        artifact = CatalogArtifact(
            id=draft.artifact_id,
            registry_id="kya",
            slug=manifest.artifact_id.rsplit(":", 1)[-1],
            artifact_type=manifest.artifact_type.value,
            name=manifest.name,
            summary=manifest.summary,
            owner_workspace_id=draft.workspace_id,
            business_owner_id=draft.business_owner_id,
            technical_owner_id=draft.technical_owner_id,
            visibility="private",
            lifecycle="draft",
        )
        version = CatalogArtifactVersion(
            id=draft.version_id,
            artifact_id=draft.artifact_id,
            version=manifest.version,
            status="draft",
            source_repository=str(manifest.source.repository),
            source_commit=manifest.source.commit.lower(),
            source_path=manifest.source.path,
            content_digest=manifest.integrity.digest.lower(),
            manifest_digest=draft.manifest_digest,
            manifest=manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
            inventory_digest=package.inventory_digest(),
            package_size=sum(item.size for item in package.files),
            file_count=len(package.files),
            has_executable_content=package.has_executable_content,
            risk=manifest.risk.value,
            created_by=draft.created_by,
        )
        files = [
            CatalogPackageFile(
                version_id=draft.version_id,
                path=item.path,
                media_type=item.media_type,
                size=item.size,
                sha256=item.sha256.lower(),
                kind=item.kind.value,
                executable=item.executable,
            )
            for item in package.files
        ]
        capability = None
        if package.capability is not None:
            capability = CatalogCapabilityManifest(
                version_id=draft.version_id,
                schema_version=package.capability.schema_version,
                runtime=package.capability.runtime,
                declaration=package.capability.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                ),
            )
        event = OutboxEvent(
            topic="artifact.draft.created",
            aggregate_type="artifact",
            aggregate_id=str(draft.artifact_id),
            correlation_id=draft.correlation_id,
            payload={
                "artifact_id": str(draft.artifact_id),
                "version_id": str(draft.version_id),
                "workspace_id": str(draft.workspace_id),
                "public_id": manifest.artifact_id,
                "version": manifest.version,
            },
        )
        try:
            async with self._sessions() as session, session.begin():
                session.add_all([artifact, version, *files, event])
                if capability is not None:
                    session.add(capability)
        except IntegrityError as error:
            raise ArtifactConflictError("artifact or version already exists") from error
        return self._record(draft)

    async def get(self, artifact_id: UUID, workspace_id: UUID) -> ArtifactRecord | None:
        async with self._sessions() as session:
            result = await session.execute(
                select(CatalogArtifact, CatalogArtifactVersion)
                .join(
                    CatalogArtifactVersion,
                    CatalogArtifactVersion.artifact_id == CatalogArtifact.id,
                )
                .where(
                    CatalogArtifact.id == artifact_id,
                    CatalogArtifact.owner_workspace_id == workspace_id,
                )
                .order_by(CatalogArtifactVersion.created_at.desc())
                .limit(1)
            )
            row = result.first()
            if row is None:
                return None
            artifact, version = row
            file_result = await session.execute(
                select(CatalogPackageFile)
                .where(CatalogPackageFile.version_id == version.id)
                .order_by(CatalogPackageFile.path)
            )
            capability_result = await session.execute(
                select(CatalogCapabilityManifest).where(
                    CatalogCapabilityManifest.version_id == version.id
                )
            )
            capability = capability_result.scalar_one_or_none()
            package_payload: dict[str, Any] = {
                "schemaVersion": "1",
                "artifact": version.manifest,
                "files": [
                    {
                        "path": item.path,
                        "mediaType": item.media_type,
                        "size": item.size,
                        "sha256": item.sha256,
                        "kind": item.kind,
                        "executable": item.executable,
                    }
                    for item in file_result.scalars().all()
                ],
            }
            if capability is not None:
                package_payload["capability"] = capability.declaration
            package = ArtifactPackage.model_validate(package_payload)
            return ArtifactRecord(
                artifact_id=artifact.id,
                version_id=version.id,
                workspace_id=artifact.owner_workspace_id,
                slug=artifact.slug,
                lifecycle=artifact.lifecycle,
                status=version.status,
                package=package,
            )

    @staticmethod
    def _record(draft: ArtifactDraft) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=draft.artifact_id,
            version_id=draft.version_id,
            workspace_id=draft.workspace_id,
            slug=draft.package.artifact.artifact_id.rsplit(":", 1)[-1],
            lifecycle="draft",
            status="draft",
            package=draft.package,
        )


__all__ = ["SqlAlchemyArtifactRegistry"]
