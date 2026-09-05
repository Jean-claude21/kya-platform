"""Released artifacts are signed, verified and revocable after compromise."""

from datetime import UTC, datetime
from uuid import UUID

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
