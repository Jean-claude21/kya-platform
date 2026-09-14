"""Machine-verifiable integrity material for an immutable artifact release."""

import base64
import hashlib
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from kya_platform.application.publication.integrity import (
    ArtifactSignature,
    TrustedSigningKey,
    signature_message,
)
from kya_platform.contracts.artifact_package import PackageFile, canonical_content_payload


class StrictIntegrityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntegrityFile(StrictIntegrityContract):
    path: str
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    included_in_content_digest: bool


class ContentVerification(StrictIntegrityContract):
    algorithm: Literal["sha-256"] = "sha-256"
    canonicalization: Literal["kya-content-inventory-v1"] = "kya-content-inventory-v1"
    encoding: Literal["utf-8"] = "utf-8"
    excluded_paths: tuple[str, ...] = ("artifact.manifest.json",)
    canonical_payload_base64: str
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: tuple[IntegrityFile, ...]


class SignatureVerificationMaterial(StrictIntegrityContract):
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str
    public_key_base64url: str
    signature_base64url: str
    signed_payload_base64url: str
    signed_at: str


class ReleaseIntegrityDocument(StrictIntegrityContract):
    schema_version: Literal["1"] = "1"
    release_id: UUID
    artifact_version_id: UUID
    artifact_slug: str
    version: str
    archive_algorithm: Literal["sha-256"] = "sha-256"
    archive_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: ContentVerification
    signature: SignatureVerificationMaterial


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def build_release_integrity_document(
    *,
    release_id: UUID,
    artifact_version_id: UUID,
    artifact_slug: str,
    version: str,
    archive_digest: str,
    files: list[PackageFile],
    signature: ArtifactSignature,
    signing_key: TrustedSigningKey,
) -> ReleaseIntegrityDocument:
    """Build a self-contained proof clients can verify without private conventions."""

    canonical = canonical_content_payload(files)
    content_digest = hashlib.sha256(canonical).hexdigest()
    if signature.artifact_version_id != artifact_version_id:
        raise ValueError("signature artifact version does not match release")
    if signature.content_digest != content_digest:
        raise ValueError("signature content digest does not match canonical inventory")
    if signature.key_id != signing_key.key_id:
        raise ValueError("signature key does not match trusted signing key")
    return ReleaseIntegrityDocument(
        release_id=release_id,
        artifact_version_id=artifact_version_id,
        artifact_slug=artifact_slug,
        version=version,
        archive_digest=archive_digest,
        content=ContentVerification(
            canonical_payload_base64=base64.b64encode(canonical).decode("ascii"),
            digest=content_digest,
            files=tuple(
                IntegrityFile(
                    path=item.path,
                    size=item.size,
                    sha256=item.sha256.lower(),
                    included_in_content_digest=item.path != "artifact.manifest.json",
                )
                for item in sorted(files, key=lambda candidate: candidate.path)
            ),
        ),
        signature=SignatureVerificationMaterial(
            key_id=signature.key_id,
            public_key_base64url=_base64url(signing_key.public_key),
            signature_base64url=signature.signature,
            signed_payload_base64url=_base64url(
                signature_message(signature.artifact_version_id, signature.content_digest)
            ),
            signed_at=signature.signed_at.isoformat(),
        ),
    )


__all__ = [
    "ContentVerification",
    "IntegrityFile",
    "ReleaseIntegrityDocument",
    "SignatureVerificationMaterial",
    "build_release_integrity_document",
]
