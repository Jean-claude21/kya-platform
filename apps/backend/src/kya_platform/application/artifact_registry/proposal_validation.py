"""Fail-closed validation of proposal packages before any human review.

Reuses the same security posture as `ArtifactArchiveValidator` (path safety, secret detection,
size limits) but operates directly on inline `ProposalPackage` content, since a proposal has no ZIP
archive and no Git commit yet.
"""

import re
import unicodedata
from pathlib import PurePosixPath

from pydantic import ValidationError

from kya_platform.contracts.artifact_package import MAX_PACKAGE_BYTES, PackageFileKind
from kya_platform.contracts.document_type import DocumentTypeDefinition
from kya_platform.contracts.proposal_package import ProposalPackage
from kya_platform.domain.catalog import ArtifactType

_TEXT_SCAN_LIMIT = 2 * 1024 * 1024
_NATIVE_SUFFIXES = frozenset({".exe", ".dll", ".so", ".dylib", ".com", ".msi"})
_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        rb"(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*"
        rb"['\"]?[A-Za-z0-9_./+=-]{16,}"
    ),
)


class ProposalValidationError(ValueError):
    """The submitted proposal package cannot safely enter the review queue."""


_REQUIRED_FILES: dict[ArtifactType, frozenset[str]] = {
    ArtifactType.SKILL: frozenset({"artifact.manifest.json", "SKILL.md"}),
    ArtifactType.APPLICATION: frozenset({"artifact.manifest.json", "package.json"}),
    ArtifactType.MCP_SERVER: frozenset(
        {"artifact.manifest.json", "capability.manifest.json", "pyproject.toml"}
    ),
    ArtifactType.DOCUMENT_TYPE: frozenset({"artifact.manifest.json", "document-type.json"}),
}


def validate_proposal_package(package: ProposalPackage, artifact_type: ArtifactType) -> None:
    """Raise ProposalValidationError for anything unsafe; never extracts or executes content."""

    required = _REQUIRED_FILES.get(artifact_type)
    if required is None:
        raise ProposalValidationError(
            "proposals currently support only skill, app, mcp-server, and document-type artifacts"
        )
    paths = {file.path for file in package.files}
    missing = sorted(required - paths)
    if missing:
        raise ProposalValidationError(
            f"{artifact_type.value} proposal is missing required files: {', '.join(missing)}"
        )

    total_size = 0
    for file in package.files:
        normalized = unicodedata.normalize("NFC", file.path)
        if normalized != file.path:
            raise ProposalValidationError(f"path must be NFC-normalized: {file.path}")
        path = PurePosixPath(file.path)
        if "\\" in file.path or "\x00" in file.path or path.is_absolute():
            raise ProposalValidationError(f"path must be relative POSIX: {file.path}")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ProposalValidationError(f"path cannot traverse: {file.path}")
        suffix = path.suffix.casefold()
        if suffix in _NATIVE_SUFFIXES:
            raise ProposalValidationError(f"native executable is not portable: {file.path}")
        content = file.decoded()
        total_size += len(content)
        if len(content) <= _TEXT_SCAN_LIMIT and any(
            pattern.search(content) for pattern in _SECRET_PATTERNS
        ):
            raise ProposalValidationError(f"probable secret detected in: {file.path}")
    if total_size > MAX_PACKAGE_BYTES:
        raise ProposalValidationError("proposal package exceeds the uncompressed size limit")
    if artifact_type is ArtifactType.DOCUMENT_TYPE:
        definition = next(file for file in package.files if file.path == "document-type.json")
        if definition.kind is not PackageFileKind.SCHEMA:
            raise ProposalValidationError("document-type.json must be classified as schema")
        try:
            DocumentTypeDefinition.model_validate_json(definition.decoded())
        except (UnicodeDecodeError, ValidationError, ValueError) as error:
            raise ProposalValidationError("document-type.json is invalid") from error


__all__ = ["ProposalValidationError", "validate_proposal_package"]
