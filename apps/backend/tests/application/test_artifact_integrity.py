"""Released artifacts are signed, verified and revocable after compromise."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.publication.integrity import (
    Ed25519ArtifactSigner,
    InMemoryTrustStore,
    SignatureVerification,
    TrustedSigningKey,
    verify_artifact_signature,
)

VERSION_ID = UUID("22222222-2222-4222-8222-222222222222")
DIGEST = "a" * 64
SIGNED_AT = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)


def signer_and_store() -> tuple[Ed25519ArtifactSigner, InMemoryTrustStore]:
    signer = Ed25519ArtifactSigner.generate("kya-release-2026-01")
    store = InMemoryTrustStore(
        (
            TrustedSigningKey(
                key_id=signer.key_id,
                public_key=signer.public_key_bytes(),
            ),
        )
    )
    return signer, store


def test_valid_release_signature_is_accepted() -> None:
    signer, store = signer_and_store()
    signature = signer.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)

    result = verify_artifact_signature(signature, expected_digest=DIGEST, trust_store=store)

    assert result is SignatureVerification.VALID
    assert "private" not in repr(signer).lower()


def test_signer_can_be_recreated_from_the_same_raw_private_key() -> None:
    generated = Ed25519ArtifactSigner.generate("kya-release-2026-01")
    restored = Ed25519ArtifactSigner.from_private_key_bytes(
        generated.key_id, generated.private_key_bytes()
    )

    signature = restored.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)
    store = InMemoryTrustStore(
        (TrustedSigningKey(key_id=restored.key_id, public_key=restored.public_key_bytes()),)
    )

    assert (
        verify_artifact_signature(signature, expected_digest=DIGEST, trust_store=store)
        is SignatureVerification.VALID
    )


def test_signer_rejects_an_invalid_raw_private_key_length() -> None:
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        Ed25519ArtifactSigner.from_private_key_bytes("kya-release-2026-01", b"short")


def test_modified_digest_is_rejected() -> None:
    signer, store = signer_and_store()
    signature = signer.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)

    result = verify_artifact_signature(signature, expected_digest="b" * 64, trust_store=store)

    assert result is SignatureVerification.DIGEST_MISMATCH


def test_signature_from_unknown_key_is_rejected() -> None:
    signer = Ed25519ArtifactSigner.generate("unknown-key")
    signature = signer.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)

    result = verify_artifact_signature(
        signature,
        expected_digest=DIGEST,
        trust_store=InMemoryTrustStore(),
    )

    assert result is SignatureVerification.UNKNOWN_KEY


def test_compromised_key_revokes_previous_releases() -> None:
    signer, store = signer_and_store()
    signature = signer.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)
    store.revoke(signer.key_id, compromised_at=datetime(2026, 9, 5, 11, 0, tzinfo=UTC))

    result = verify_artifact_signature(signature, expected_digest=DIGEST, trust_store=store)

    assert result is SignatureVerification.KEY_REVOKED


def test_tampered_signature_is_rejected() -> None:
    signer, store = signer_and_store()
    signature = signer.sign(VERSION_ID, DIGEST, signed_at=SIGNED_AT)
    tampered = signature.model_copy(update={"signature": "AAAA"})

    result = verify_artifact_signature(tampered, expected_digest=DIGEST, trust_store=store)

    assert result is SignatureVerification.INVALID_SIGNATURE
