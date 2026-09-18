"""Public, content-addressed download and verification for signed builtin releases."""

import hashlib

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy import select

from kya_platform.application.artifact_registry.release_package import (
    PreparedProposalRelease,
    prepare_proposal_release,
)
from kya_platform.application.publication.integrity import ArtifactSignature, InMemoryTrustStore
from kya_platform.contracts.artifact_package import PackageFile, PackageFileKind
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.contracts.release_integrity import (
    ReleaseIntegrityDocument,
    build_release_integrity_document,
)
from kya_platform.domain.catalog import ArtifactType
from kya_platform.infrastructure.database.builtin_artifacts import (
    _ARCHIVE_DIGESTS,
    design_system_archive_bytes,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogPackageFile,
    CatalogProposal,
    CatalogRelease,
)

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/kya-design-system/{version}/package", response_class=Response)
async def download_design_system_release(version: str) -> Response:
    """Return the immutable signed package; authorization still gates its discovery."""

    digest = _ARCHIVE_DIGESTS.get(version)
    if digest is None:
        raise HTTPException(status_code=404, detail="release not found")
    return Response(
        content=design_system_archive_bytes(version),
        media_type="application/zip",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Digest": f"sha-256={digest}",
            "Content-Disposition": f'attachment; filename="kya-design-system-{version}.zip"',
        },
    )


@router.get(
    "/kya-design-system/{version}/integrity",
    response_model=ReleaseIntegrityDocument,
)
async def verify_design_system_release(version: str, request: Request) -> ReleaseIntegrityDocument:
    """Expose the exact content and signature proof required by an installing client."""

    sessions = getattr(request.app.state, "catalog_sessions", None)
    trust_store = getattr(request.app.state, "artifact_trust_store", None)
    if sessions is None or not isinstance(trust_store, InMemoryTrustStore):
        raise HTTPException(status_code=503, detail="release integrity service unavailable")
    async with sessions() as session:
        result = await session.execute(
            select(CatalogRelease, CatalogArtifactVersion, CatalogArtifact)
            .join(
                CatalogArtifactVersion,
                CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
            )
            .join(CatalogArtifact, CatalogArtifact.id == CatalogArtifactVersion.artifact_id)
            .where(
                CatalogArtifact.slug == "kya-design-system",
                CatalogArtifactVersion.version == version,
                CatalogRelease.status == "published",
            )
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=404, detail="release not found")
        release, version_row, artifact = row
        file_rows = (
            (
                await session.execute(
                    select(CatalogPackageFile)
                    .where(CatalogPackageFile.version_id == version_row.id)
                    .order_by(CatalogPackageFile.path)
                )
            )
            .scalars()
            .all()
        )
    try:
        signature = ArtifactSignature.model_validate(release.signature)
        signing_key = trust_store.get(signature.key_id)
        if signing_key is None:
            raise ValueError("release signing key is not trusted")
        files = [
            PackageFile(
                path=item.path,
                media_type=item.media_type,
                size=item.size,
                sha256=item.sha256,
                kind=PackageFileKind(item.kind),
                executable=item.executable,
            )
            for item in file_rows
        ]
        archive = design_system_archive_bytes(version)
        return build_release_integrity_document(
            release_id=release.id,
            artifact_version_id=version_row.id,
            artifact_slug=artifact.slug,
            version=version_row.version,
            archive_digest=hashlib.sha256(archive).hexdigest(),
            files=files,
            signature=signature,
            signing_key=signing_key,
        )
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=503, detail="release integrity proof invalid") from error


async def _proposal_release(
    request: Request, slug: str, version: str
) -> tuple[
    CatalogRelease,
    CatalogArtifactVersion,
    CatalogArtifact,
    list[CatalogPackageFile],
    PreparedProposalRelease,
]:
    sessions = getattr(request.app.state, "catalog_sessions", None)
    if sessions is None:
        raise HTTPException(status_code=503, detail="release service unavailable")
    async with sessions() as session:
        result = await session.execute(
            select(CatalogRelease, CatalogArtifactVersion, CatalogArtifact, CatalogProposal)
            .join(
                CatalogArtifactVersion,
                CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
            )
            .join(CatalogArtifact, CatalogArtifact.id == CatalogArtifactVersion.artifact_id)
            .join(
                CatalogProposal,
                CatalogProposal.resulting_artifact_version_id == CatalogArtifactVersion.id,
            )
            .where(
                CatalogArtifact.slug == slug,
                CatalogArtifactVersion.version == version,
                CatalogArtifactVersion.status == "published",
                CatalogRelease.status == "published",
                CatalogProposal.status == "merged",
            )
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=404, detail="release not found")
        release, version_row, artifact, proposal = row
        file_rows = (
            (
                await session.execute(
                    select(CatalogPackageFile)
                    .where(CatalogPackageFile.version_id == version_row.id)
                    .order_by(CatalogPackageFile.path)
                )
            )
            .scalars()
            .all()
        )
    try:
        prepared = prepare_proposal_release(
            proposal_package=ProposalPackage.model_validate(proposal.package),
            slug=artifact.slug,
            artifact_type=ArtifactType(artifact.artifact_type),
            source_repository=version_row.source_repository,
            source_commit=version_row.source_commit,
            source_path=version_row.source_path or "",
        )
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=503, detail="release package is invalid") from error
    return release, version_row, artifact, file_rows, prepared


@router.get("/{slug}/{version}/package", response_class=Response)
async def download_proposal_release(slug: str, version: str, request: Request) -> Response:
    """Serve the deterministic package built from the reviewed and merged proposal."""

    _release, _version_row, _artifact, _file_rows, prepared = await _proposal_release(
        request, slug, version
    )
    return Response(
        content=prepared.archive,
        media_type="application/zip",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Digest": f"sha-256={prepared.archive_digest}",
            "Content-Disposition": f'attachment; filename="{slug}-{version}.zip"',
        },
    )


@router.get("/{slug}/{version}/integrity", response_model=ReleaseIntegrityDocument)
async def verify_proposal_release(
    slug: str, version: str, request: Request
) -> ReleaseIntegrityDocument:
    """Return the signature and exact archive digest used by installing clients."""

    trust_store = getattr(request.app.state, "artifact_trust_store", None)
    if not isinstance(trust_store, InMemoryTrustStore):
        raise HTTPException(status_code=503, detail="release integrity service unavailable")
    release, version_row, artifact, file_rows, prepared = await _proposal_release(
        request, slug, version
    )
    try:
        signature = ArtifactSignature.model_validate(release.signature)
        signing_key = trust_store.get(signature.key_id)
        if signing_key is None:
            raise ValueError("release signing key is not trusted")
        files = [
            PackageFile(
                path=item.path,
                media_type=item.media_type,
                size=item.size,
                sha256=item.sha256,
                kind=PackageFileKind(item.kind),
                executable=item.executable,
            )
            for item in file_rows
        ]
        return build_release_integrity_document(
            release_id=release.id,
            artifact_version_id=version_row.id,
            artifact_slug=artifact.slug,
            version=version_row.version,
            archive_digest=prepared.archive_digest,
            files=files,
            signature=signature,
            signing_key=signing_key,
        )
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=503, detail="release integrity proof invalid") from error


__all__ = ["router"]
