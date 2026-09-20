"""Deterministically turn an approved proposal into an immutable release package."""

import hashlib
import io
import json
import mimetypes
import zipfile
from dataclasses import dataclass

from kya_platform.contracts.artifact_manifest import ArtifactManifest
from kya_platform.contracts.artifact_package import (
    ArtifactPackage,
    CapabilityManifest,
    PackageFile,
    PackageFileKind,
    canonical_content_payload,
)
from kya_platform.contracts.document_type import DocumentTypeDefinition
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType


@dataclass(frozen=True, slots=True)
class PreparedProposalRelease:
    package: ArtifactPackage
    archive: bytes
    archive_digest: str
    manifest_bytes: bytes


def _media_type(path: str) -> str:
    if path.endswith(".md"):
        return "text/markdown"
    if path.endswith(".json"):
        return "application/json"
    guessed, _encoding = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _file(path: str, content: bytes, kind: PackageFileKind) -> PackageFile:
    return PackageFile(
        path=path,
        media_type=_media_type(path),
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        kind=kind,
        executable=kind is PackageFileKind.SCRIPT,
    )


def _archive(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, files[path])
    return output.getvalue()


def prepare_proposal_release(
    *,
    proposal_package: ProposalPackage,
    slug: str,
    artifact_type: ArtifactType,
    source_repository: str,
    source_commit: str,
    source_path: str,
) -> PreparedProposalRelease:
    """Normalize server-owned provenance and integrity without trusting client assertions."""

    submitted = {item.path: item for item in proposal_package.files}
    try:
        raw_manifest = json.loads(submitted["artifact.manifest.json"].decoded())
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("proposal artifact manifest must be valid UTF-8 JSON") from error
    if not isinstance(raw_manifest, dict):
        raise ValueError("proposal artifact manifest must be a JSON object")
    expected_id = f"kya:{artifact_type.value}:{slug}"
    if raw_manifest.get("id") != expected_id or raw_manifest.get("type") != artifact_type.value:
        raise ValueError("proposal manifest identity does not match its type and slug")

    content_by_path = {
        path: item.decoded() for path, item in submitted.items() if path != "artifact.manifest.json"
    }
    inventory_without_manifest = [
        _file(path, content, submitted[path].kind)
        for path, content in sorted(content_by_path.items())
    ]
    content_digest = hashlib.sha256(
        canonical_content_payload(inventory_without_manifest)
    ).hexdigest()
    normalized_manifest = dict(raw_manifest)
    normalized_manifest["source"] = {
        "repository": source_repository,
        "commit": source_commit.lower(),
        "path": source_path,
    }
    normalized_manifest["integrity"] = {"algorithm": "sha256", "digest": content_digest}
    manifest = ArtifactManifest.model_validate(normalized_manifest)
    if artifact_type is ArtifactType.DOCUMENT_TYPE:
        try:
            document_type = DocumentTypeDefinition.model_validate_json(
                content_by_path["document-type.json"]
            )
        except (KeyError, UnicodeDecodeError, ValueError) as error:
            raise ValueError("proposal document type definition is invalid") from error
        if document_type.document_type_id != manifest.artifact_id:
            raise ValueError("document type id does not match the artifact manifest")
        if document_type.version != manifest.version:
            raise ValueError("document type version does not match the artifact manifest")
    manifest_bytes = (
        json.dumps(
            manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode()
    content_by_path["artifact.manifest.json"] = manifest_bytes
    inventory = [
        _file(path, content, submitted[path].kind)
        if path in submitted and path != "artifact.manifest.json"
        else _file(path, content, PackageFileKind.MANIFEST)
        for path, content in sorted(content_by_path.items())
    ]
    capability = None
    if "capability.manifest.json" in content_by_path:
        try:
            capability = CapabilityManifest.model_validate_json(
                content_by_path["capability.manifest.json"]
            )
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError("capability manifest is invalid") from error
    package = ArtifactPackage(
        schema_version="1",
        artifact=manifest,
        files=inventory,
        capability=capability,
    )
    archive = _archive(content_by_path)
    return PreparedProposalRelease(
        package=package,
        archive=archive,
        archive_digest=hashlib.sha256(archive).hexdigest(),
        manifest_bytes=manifest_bytes,
    )


__all__ = ["PreparedProposalRelease", "prepare_proposal_release"]
