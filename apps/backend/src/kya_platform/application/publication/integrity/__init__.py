"""Ed25519 signing and fail-closed trust decisions for released artifacts."""

import base64
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

_SIGNATURE_DOMAIN = b"KYA-PLATFORM-ARTIFACT-SIGNATURE-V1\x00"


class ArtifactSignature(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_version_id: UUID
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    key_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    algorithm: str = Field(default="Ed25519", pattern=r"^Ed25519$")
    signature: str = Field(min_length=1, max_length=128)
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("signature time must be timezone-aware")
        return value


class SignatureVerification(StrEnum):
    VALID = "valid"
    DIGEST_MISMATCH = "digest_mismatch"
    UNKNOWN_KEY = "unknown_key"
    KEY_REVOKED = "key_revoked"
    INVALID_SIGNATURE = "invalid_signature"


class TrustedSigningKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    public_key: bytes = Field(min_length=32, max_length=32)
    compromised_at: datetime | None = None


class InMemoryTrustStore:
    def __init__(self, keys: Iterable[TrustedSigningKey] = ()) -> None:
        self._keys = {key.key_id: key for key in keys}

    def get(self, key_id: str) -> TrustedSigningKey | None:
        return self._keys.get(key_id)

    def revoke(self, key_id: str, *, compromised_at: datetime) -> None:
        if compromised_at.tzinfo is None:
            raise ValueError("compromise time must be timezone-aware")
        key = self._keys.get(key_id)
        if key is None:
            raise KeyError(key_id)
        self._keys[key_id] = key.model_copy(update={"compromised_at": compromised_at})


def _message(artifact_version_id: UUID, content_digest: str) -> bytes:
    return _SIGNATURE_DOMAIN + artifact_version_id.bytes + bytes.fromhex(content_digest)


class Ed25519ArtifactSigner:
    """Keep private key material opaque while signing a domain-separated payload."""

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        TrustedSigningKey(key_id=key_id, public_key=b"0" * 32)
        self.key_id = key_id
        self._private_key = private_key

    @classmethod
    def generate(cls, key_id: str) -> Ed25519ArtifactSigner:
        return cls(key_id, Ed25519PrivateKey.generate())

    @classmethod
    def from_private_key_bytes(cls, key_id: str, private_key: bytes) -> Ed25519ArtifactSigner:
        if len(private_key) != 32:
            raise ValueError("Ed25519 private key must contain exactly 32 bytes")
        return cls(key_id, Ed25519PrivateKey.from_private_bytes(private_key))

    def private_key_bytes(self) -> bytes:
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def __repr__(self) -> str:
        return f"Ed25519ArtifactSigner(key_id={self.key_id!r}, key_material='**********')"

    def public_key_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(
        self,
        artifact_version_id: UUID,
        content_digest: str,
        *,
        signed_at: datetime,
    ) -> ArtifactSignature:
        unsigned = ArtifactSignature(
            artifact_version_id=artifact_version_id,
            content_digest=content_digest,
            key_id=self.key_id,
            signature="pending",
            signed_at=signed_at,
        )
        raw_signature = self._private_key.sign(_message(artifact_version_id, content_digest))
        encoded = base64.urlsafe_b64encode(raw_signature).rstrip(b"=").decode("ascii")
        return unsigned.model_copy(update={"signature": encoded})


def verify_artifact_signature(
    signature: ArtifactSignature,
    *,
    expected_digest: str,
    trust_store: InMemoryTrustStore,
) -> SignatureVerification:
    if signature.content_digest != expected_digest:
        return SignatureVerification.DIGEST_MISMATCH
    trusted_key = trust_store.get(signature.key_id)
    if trusted_key is None:
        return SignatureVerification.UNKNOWN_KEY
    if trusted_key.compromised_at is not None:
        return SignatureVerification.KEY_REVOKED
    try:
        padding = "=" * (-len(signature.signature) % 4)
        raw_signature = base64.b64decode(
            signature.signature + padding,
            altchars=b"-_",
            validate=True,
        )
        Ed25519PublicKey.from_public_bytes(trusted_key.public_key).verify(
            raw_signature,
            _message(signature.artifact_version_id, signature.content_digest),
        )
    except InvalidSignature, ValueError:
        return SignatureVerification.INVALID_SIGNATURE
    return SignatureVerification.VALID


__all__ = [
    "ArtifactSignature",
    "Ed25519ArtifactSigner",
    "InMemoryTrustStore",
    "SignatureVerification",
    "TrustedSigningKey",
    "verify_artifact_signature",
]
