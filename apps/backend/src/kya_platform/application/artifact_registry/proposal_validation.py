"""Fail-closed validation of proposal packages before any human review.

Reuses the same security posture as `ArtifactArchiveValidator` (path safety, secret detection,
size limits) but operates directly on inline `ProposalPackage` content, since a proposal has no ZIP
archive and no Git commit yet.
"""

import re
import unicodedata
from pathlib import PurePosixPath

from kya_platform.contracts.artifact_package import MAX_PACKAGE_BYTES
from kya_platform.contracts.proposal_package import ProposalPackage

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


def validate_proposal_package(package: ProposalPackage) -> None:
    """Raise ProposalValidationError for anything unsafe; never extracts or executes content."""

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


__all__ = ["ProposalValidationError", "validate_proposal_package"]
