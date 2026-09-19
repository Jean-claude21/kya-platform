"""Fail-closed validation of portable artifact ZIP archives.

The validator reads bytes and metadata only. It never extracts files to disk and never
imports or executes packaged code.
"""

import hashlib
import io
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TypeVar

from pydantic import ValidationError

from kya_platform.contracts.artifact_manifest import ArtifactManifest, ArtifactType
from kya_platform.contracts.artifact_package import (
    MAX_PACKAGE_BYTES,
    MAX_PACKAGE_FILES,
    ArtifactPackage,
    CapabilityManifest,
    PackageFile,
    PackageFileKind,
    canonical_content_payload,
)
from kya_platform.contracts.document_type import DocumentTypeDefinition

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
_TEXT_SCAN_LIMIT = 2 * 1024 * 1024
_EXECUTABLE_SUFFIXES = frozenset({".py", ".sh", ".ps1", ".js", ".mjs", ".ts"})
_NATIVE_SUFFIXES = frozenset({".exe", ".dll", ".so", ".dylib", ".com", ".msi"})
_MACRO_SUFFIXES = frozenset({".docm", ".xlsm", ".pptm"})
_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        rb"(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*"
        rb"['\"]?[A-Za-z0-9_./+=-]{16,}"
    ),
)
_ContractT = TypeVar("_ContractT", ArtifactManifest, CapabilityManifest, DocumentTypeDefinition)


class ArchiveValidationError(ValueError):
    """The submitted archive cannot safely enter the registry."""


@dataclass(frozen=True, slots=True)
class ValidatedArchive:
    package: ArtifactPackage
    archive_digest: str


def calculate_payload_digest(files: list[PackageFile]) -> str:
    """Digest content without the self-referential artifact manifest."""

    return hashlib.sha256(canonical_content_payload(files)).hexdigest()


def _kind(path: str) -> PackageFileKind:
    if path in {"artifact.manifest.json", "capability.manifest.json", "sbom.cdx.json"}:
        return PackageFileKind.MANIFEST
    if path == "document-type.json":
        return PackageFileKind.SCHEMA
    if path == "SKILL.md":
        return PackageFileKind.INSTRUCTION
    prefix = PurePosixPath(path).parts[0]
    mapping = {
        "agents": PackageFileKind.METADATA,
        "references": PackageFileKind.REFERENCE,
        "templates": PackageFileKind.TEMPLATE,
        "schemas": PackageFileKind.SCHEMA,
        "scripts": PackageFileKind.SCRIPT,
        "tests": PackageFileKind.TEST,
        "assets": PackageFileKind.ASSET,
        "examples": PackageFileKind.REFERENCE,
    }
    try:
        return mapping[prefix]
    except KeyError as error:
        raise ArchiveValidationError(f"unsupported package path: {path}") from error


def _media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.casefold()
    return {
        ".json": "application/json",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".sh": "text/x-shellscript",
        ".ps1": "text/plain",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".ts": "text/typescript",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")


def _validate_skill_frontmatter(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArchiveValidationError("SKILL.md must be valid UTF-8") from error
    lines = text.splitlines()
    if len(lines) < 4 or lines[0].strip() != "---":
        raise ArchiveValidationError("SKILL.md requires YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as error:
        raise ArchiveValidationError("SKILL.md frontmatter is not closed") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip("'\"")
    if not fields.get("name") or not fields.get("description"):
        raise ArchiveValidationError("SKILL.md frontmatter requires name and description")
    return fields


def _validate_sbom(content: bytes) -> None:
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveValidationError("sbom.cdx.json must be valid CycloneDX JSON") from error
    if not isinstance(payload, dict) or payload.get("bomFormat") != "CycloneDX":
        raise ArchiveValidationError("sbom.cdx.json must declare the CycloneDX format")


class ArtifactArchiveValidator:
    """Validate a ZIP archive deterministically without extracting or executing it."""

    def validate(self, archive: bytes) -> ValidatedArchive:
        if not archive or len(archive) > MAX_ARCHIVE_BYTES:
            raise ArchiveValidationError("archive size is outside the allowed range")
        try:
            zipped = zipfile.ZipFile(io.BytesIO(archive))
        except zipfile.BadZipFile as error:
            raise ArchiveValidationError("archive is not a valid ZIP file") from error

        with zipped:
            entries = [item for item in zipped.infolist() if not item.is_dir()]
            if not entries or len(entries) > MAX_PACKAGE_FILES:
                raise ArchiveValidationError("archive file count is outside the allowed range")
            if sum(item.file_size for item in entries) > MAX_PACKAGE_BYTES:
                raise ArchiveValidationError("archive exceeds the uncompressed size limit")

            files: list[PackageFile] = []
            contents: dict[str, bytes] = {}
            seen: set[str] = set()
            for entry in entries:
                path = entry.filename
                try:
                    PackageFile(
                        path=path,
                        media_type="application/octet-stream",
                        size=entry.file_size,
                        sha256="0" * 64,
                        kind=PackageFileKind.ASSET,
                    )
                except ValidationError as error:
                    raise ArchiveValidationError(f"unsafe package path: {path}") from error
                folded = path.casefold()
                if folded in seen:
                    raise ArchiveValidationError("archive paths cannot differ only by case")
                seen.add(folded)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ArchiveValidationError(f"symbolic links are forbidden: {path}")
                if entry.flag_bits & 0x1:
                    raise ArchiveValidationError(f"encrypted entries are forbidden: {path}")
                if entry.compress_size == 0 and entry.file_size > 0:
                    raise ArchiveValidationError(f"invalid compression metadata: {path}")
                if (
                    entry.file_size > 1024 * 1024
                    and entry.file_size > entry.compress_size * MAX_COMPRESSION_RATIO
                ):
                    raise ArchiveValidationError(f"suspicious compression ratio: {path}")
                suffix = PurePosixPath(path).suffix.casefold()
                if suffix in _NATIVE_SUFFIXES:
                    raise ArchiveValidationError(f"native executable is not portable: {path}")
                content = zipped.read(entry)
                if len(content) != entry.file_size:
                    raise ArchiveValidationError(f"archive entry size mismatch: {path}")
                if len(content) <= _TEXT_SCAN_LIMIT and any(
                    pattern.search(content) for pattern in _SECRET_PATTERNS
                ):
                    raise ArchiveValidationError(f"probable secret detected in: {path}")
                kind = _kind(path)
                is_executable = (
                    kind is PackageFileKind.SCRIPT
                    or suffix in _EXECUTABLE_SUFFIXES
                    or suffix in _MACRO_SUFFIXES
                    or bool(mode & 0o111)
                )
                files.append(
                    PackageFile(
                        path=path,
                        media_type=_media_type(path),
                        size=len(content),
                        sha256=hashlib.sha256(content).hexdigest(),
                        kind=kind,
                        executable=is_executable,
                    )
                )
                contents[path] = content

        manifest = self._json_model(contents, "artifact.manifest.json", ArtifactManifest)
        capability = None
        if "capability.manifest.json" in contents:
            capability = self._json_model(contents, "capability.manifest.json", CapabilityManifest)
        try:
            package = ArtifactPackage(
                schema_version="1", artifact=manifest, files=files, capability=capability
            )
        except ValidationError as error:
            raise ArchiveValidationError(f"invalid package contract: {error}") from error
        expected_digest = calculate_payload_digest(files)
        if manifest.integrity.digest.casefold() != expected_digest:
            raise ArchiveValidationError("manifest content digest does not match the archive")
        if manifest.artifact_type is ArtifactType.SKILL:
            frontmatter = _validate_skill_frontmatter(contents["SKILL.md"])
            expected_name = manifest.artifact_id.rsplit(":", 1)[-1]
            if frontmatter["name"] != expected_name:
                raise ArchiveValidationError("SKILL.md name must match the artifact slug")
        if manifest.artifact_type is ArtifactType.DOCUMENT_TYPE:
            definition = self._json_model(contents, "document-type.json", DocumentTypeDefinition)
            expected_id = manifest.artifact_id
            if definition.document_type_id != expected_id:
                raise ArchiveValidationError("document type id must match the artifact manifest")
            if definition.version != manifest.version:
                raise ArchiveValidationError(
                    "document type version must match the artifact manifest"
                )
        if package.has_executable_content:
            if "sbom.cdx.json" not in contents:
                raise ArchiveValidationError("executable packages require sbom.cdx.json")
            _validate_sbom(contents["sbom.cdx.json"])
            if not any(item.kind is PackageFileKind.TEST for item in files):
                raise ArchiveValidationError("executable packages require declared tests")
            assert package.capability is not None
            missing = set(package.capability.entrypoints.values()) - contents.keys()
            if missing:
                raise ArchiveValidationError("capability entrypoints must exist in the archive")
            by_path = {item.path: item for item in files}
            if any(
                not by_path[path].executable for path in package.capability.entrypoints.values()
            ):
                raise ArchiveValidationError("capability entrypoints must be executable content")
        return ValidatedArchive(package, hashlib.sha256(archive).hexdigest())

    @staticmethod
    def _json_model(contents: dict[str, bytes], path: str, model: type[_ContractT]) -> _ContractT:
        try:
            payload = contents[path].decode("utf-8")
            return model.model_validate_json(payload)
        except KeyError as error:
            raise ArchiveValidationError(f"required file is missing: {path}") from error
        except (UnicodeDecodeError, ValidationError, ValueError) as error:
            raise ArchiveValidationError(f"invalid JSON contract: {path}") from error


__all__ = [
    "MAX_ARCHIVE_BYTES",
    "ArchiveValidationError",
    "ArtifactArchiveValidator",
    "ValidatedArchive",
    "calculate_payload_digest",
]
