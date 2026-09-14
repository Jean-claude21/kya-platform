"""Clients receive enough material to verify every installed byte and signature."""

import base64
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException

from kya_platform.api.routes.releases import verify_design_system_release
from kya_platform.application.artifact_registry.archive import ArtifactArchiveValidator
from kya_platform.application.publication.integrity import (
    Ed25519ArtifactSigner,
    InMemoryTrustStore,
    TrustedSigningKey,
)
from kya_platform.contracts.release_integrity import build_release_integrity_document
from kya_platform.infrastructure.database.builtin_artifacts import design_system_archive_bytes


def _decode_base64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_integrity_document_proves_files_digest_and_signature() -> None:
    archive = design_system_archive_bytes()
    package = ArtifactArchiveValidator().validate(archive).package
    version_id = uuid4()
    signer = Ed25519ArtifactSigner.generate("test-key")
    signature = signer.sign(
        version_id,
        package.artifact.integrity.digest,
        signed_at=datetime.now(UTC),
    )
    document = build_release_integrity_document(
        release_id=uuid4(),
        artifact_version_id=version_id,
        artifact_slug="kya-design-system",
        version="0.1.1",
        archive_digest=hashlib.sha256(archive).hexdigest(),
        files=package.files,
        signature=signature,
        signing_key=TrustedSigningKey(
            key_id=signer.key_id,
            public_key=signer.public_key_bytes(),
        ),
    )

    canonical = base64.b64decode(document.content.canonical_payload_base64)
    assert hashlib.sha256(canonical).hexdigest() == document.content.digest
    assert document.content.digest == package.artifact.integrity.digest
    assert len(document.content.files) == 7
    assert document.content.excluded_paths == ("artifact.manifest.json",)
    Ed25519PublicKey.from_public_bytes(
        _decode_base64url(document.signature.public_key_base64url)
    ).verify(
        _decode_base64url(document.signature.signature_base64url),
        _decode_base64url(document.signature.signed_payload_base64url),
    )


@pytest.mark.asyncio
async def test_integrity_route_fails_closed_without_runtime_trust() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(HTTPException) as captured:
        await verify_design_system_release(request)  # type: ignore[arg-type]

    assert captured.value.status_code == 503


@pytest.mark.asyncio
async def test_integrity_route_returns_verifiable_runtime_release() -> None:
    archive = design_system_archive_bytes()
    package = ArtifactArchiveValidator().validate(archive).package
    version_id = uuid4()
    release_id = uuid4()
    signer = Ed25519ArtifactSigner.generate("test-key")
    signature = signer.sign(
        version_id,
        package.artifact.integrity.digest,
        signed_at=datetime.now(UTC),
    )
    release = SimpleNamespace(
        id=release_id,
        signature=signature.model_dump(mode="json"),
    )
    version = SimpleNamespace(id=version_id, version="0.1.1")
    artifact = SimpleNamespace(slug="kya-design-system")
    file_rows = [
        SimpleNamespace(
            version_id=version_id,
            path=item.path,
            media_type=item.media_type,
            size=item.size,
            sha256=item.sha256,
            kind=item.kind.value,
            executable=item.executable,
        )
        for item in package.files
    ]

    class Result:
        def __init__(self, value: object) -> None:
            self.value = value

        def first(self) -> object:
            return self.value

        def scalars(self) -> Result:
            return self

        def all(self) -> object:
            return self.value

    class Session:
        def __init__(self) -> None:
            self.calls = 0

        async def __aenter__(self) -> Session:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def execute(self, _statement: object) -> Result:
            self.calls += 1
            return Result((release, version, artifact) if self.calls == 1 else file_rows)

    trust_store = InMemoryTrustStore(
        (
            TrustedSigningKey(
                key_id=signer.key_id,
                public_key=signer.public_key_bytes(),
            ),
        )
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                catalog_sessions=Session,
                artifact_trust_store=trust_store,
            )
        )
    )

    document = await verify_design_system_release(request)  # type: ignore[arg-type]

    assert document.release_id == release_id
    assert document.content.digest == package.artifact.integrity.digest
