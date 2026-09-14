"""Idempotent recovery of KYA-owned builtin artifact releases.

This narrow reconciler exists because the first Design System release was signed with
distribution metadata that no longer identifies its package bytes.  It never mutates that
historical release.  Instead it verifies a fixed, immutable archive and creates a new signed
release once.  Normal user-authored releases continue through the governed publication flow.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid7

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.artifact_registry.archive import ArtifactArchiveValidator
from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogPackageFile,
    CatalogRelease,
    OutboxEvent,
)

_VERSION = "0.1.1"
_ARCHIVE_URL = (
    "https://api.kya-platform.vttlife.com/api/v1/releases/"
    "kya-design-system/0.1.1/package"
)
_ARCHIVE_DIGEST = "0d85fbe28422c84b33daa5ef397b4b8e3a5c3469c265ad10c5ab5d01dba471a6"


def design_system_archive_bytes() -> bytes:
    """Read and verify the packaged builtin release from the application image."""

    candidates = (
        Path("/app/catalog/releases/kya-design-system/0.1.1.zip"),
        Path("catalog/releases/kya-design-system/0.1.1.zip"),
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("builtin Design System archive is unavailable")
    archive = path.read_bytes()
    if hashlib.sha256(archive).hexdigest() != _ARCHIVE_DIGEST:
        raise RuntimeError("builtin Design System archive digest mismatch")
    return archive


async def ensure_design_system_recovery_release(
    sessions: async_sessionmaker[AsyncSession],
    signer: Ed25519ArtifactSigner,
) -> bool:
    """Create the corrective release exactly once; return whether a row was added."""

    async with sessions() as session:
        artifact = await session.scalar(
            select(CatalogArtifact).where(
                CatalogArtifact.registry_id == "kya",
                CatalogArtifact.artifact_type == "skill",
                CatalogArtifact.slug == "kya-design-system",
            )
        )
        if artifact is None:
            return False
        existing = await session.scalar(
            select(CatalogArtifactVersion.id).where(
                CatalogArtifactVersion.artifact_id == artifact.id,
                CatalogArtifactVersion.version == _VERSION,
            )
        )
        if existing is not None:
            return False

    archive = design_system_archive_bytes()
    package = ArtifactArchiveValidator().validate(archive).package
    if package.artifact.version != _VERSION:
        raise RuntimeError("builtin Design System archive version mismatch")

    manifest = package.artifact.model_dump(mode="json", by_alias=True, exclude_none=True)
    canonical_manifest = json.dumps(
        manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    now = datetime.now(UTC)
    version_id = uuid7()
    release_id = uuid7()
    signature = signer.sign(version_id, package.artifact.integrity.digest, signed_at=now)

    async with sessions() as session, session.begin():
        artifact = await session.scalar(
            select(CatalogArtifact)
            .where(
                CatalogArtifact.registry_id == "kya",
                CatalogArtifact.artifact_type == "skill",
                CatalogArtifact.slug == "kya-design-system",
            )
            .with_for_update()
        )
        if artifact is None:
            return False
        existing = await session.scalar(
            select(CatalogArtifactVersion.id).where(
                CatalogArtifactVersion.artifact_id == artifact.id,
                CatalogArtifactVersion.version == _VERSION,
            )
        )
        if existing is not None:
            return False
        source = package.artifact.source
        version = CatalogArtifactVersion(
            id=version_id,
            artifact_id=artifact.id,
            version=_VERSION,
            status="published",
            source_repository=str(source.repository),
            source_commit=source.commit.lower(),
            source_path=source.path,
            content_digest=package.artifact.integrity.digest.lower(),
            manifest_digest=hashlib.sha256(canonical_manifest.encode()).hexdigest(),
            manifest=manifest,
            inventory_digest=package.inventory_digest(),
            package_size=sum(item.size for item in package.files),
            file_count=len(package.files),
            has_executable_content=package.has_executable_content,
            risk=package.artifact.risk.value,
            created_by=artifact.technical_owner_id,
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
            for item in package.files
        ]
        release = CatalogRelease(
            id=release_id,
            artifact_version_id=version_id,
            content_digest=package.artifact.integrity.digest.lower(),
            signature=signature.model_dump(mode="json"),
            storage_locator=_ARCHIVE_URL,
            status="published",
            published_at=now,
            published_by=artifact.technical_owner_id,
        )
        artifact.lifecycle = "published"
        session.add_all(
            [
                version,
                *files,
                release,
                OutboxEvent(
                    topic="artifact.release.recovered",
                    aggregate_type="artifact_version",
                    aggregate_id=str(version_id),
                    correlation_id=release_id,
                    payload={
                        "artifact_id": str(artifact.id),
                        "version": _VERSION,
                        "release_id": str(release_id),
                        "reason": "replace-unresolvable-initial-distribution",
                    },
                ),
            ]
        )
    return True


__all__ = ["design_system_archive_bytes", "ensure_design_system_recovery_release"]
