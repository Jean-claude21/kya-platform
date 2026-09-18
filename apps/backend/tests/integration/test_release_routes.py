"""Release downloads are stable and independently verifiable."""

import base64
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Self
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from kya_platform.api.routes import releases
from kya_platform.application.artifact_registry.release_package import prepare_proposal_release
from kya_platform.application.publication.integrity import (
    Ed25519ArtifactSigner,
    InMemoryTrustStore,
    TrustedSigningKey,
)
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType


def test_design_system_release_is_downloadable_with_immutable_headers(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/releases/kya-design-system/0.1.1/package")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["digest"] == (
        "sha-256=0d85fbe28422c84b33daa5ef397b4b8e3a5c3469c265ad10c5ab5d01dba471a6"
    )
    assert hashlib.sha256(response.content).hexdigest() == response.headers["digest"].removeprefix(
        "sha-256="
    )


def test_current_design_system_release_is_downloadable(client: TestClient) -> None:
    response = client.get("/api/v1/releases/kya-design-system/0.1.2/package")

    assert response.status_code == 200
    assert response.headers["digest"] == (
        "sha-256=90f4dba0079d6b504ba66d65eddb29c64e272337312bde648abac3a2fcdea64e"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="kya-design-system-0.1.2.zip"'
    )


def test_unknown_builtin_release_is_not_disclosed(client: TestClient) -> None:
    response = client.get("/api/v1/releases/kya-design-system/9.9.9/package")

    assert response.status_code == 404


def _proposal_release():
    manifest = {
        "schemaVersion": "1",
        "id": "kya:skill:technical-brief",
        "type": "skill",
        "name": "Technical Brief",
        "version": "0.1.0",
        "summary": "A governed brief.",
        "owners": {"business": "communication", "technical": "cvsi", "workspace": "team"},
        "compatibility": {"claude-code": ">=2026-09"},
        "dependencies": [],
        "scopes": ["skill.discover"],
        "risk": "read",
    }
    encoded = base64.b64encode(json.dumps(manifest).encode()).decode()
    package = ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                contentBase64=encoded,
            ),
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                contentBase64=base64.b64encode(b"# Technical Brief\n").decode(),
            ),
        ]
    )
    return prepare_proposal_release(
        proposal_package=package,
        slug="technical-brief",
        artifact_type=ArtifactType.SKILL,
        source_repository="https://github.com/kya/platform",
        source_commit="a" * 40,
        source_path="catalog/templates/skill/technical-brief",
    )


@pytest.mark.asyncio
async def test_proposal_release_download_uses_reviewed_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _proposal_release()

    async def resolved(*_args: object):
        return object(), object(), object(), [], prepared

    monkeypatch.setattr(releases, "_proposal_release", resolved)
    response = await releases.download_proposal_release(
        "technical-brief", "0.1.0", SimpleNamespace()
    )

    assert response.body == prepared.archive
    assert response.headers["digest"] == f"sha-256={prepared.archive_digest}"
    assert response.headers["content-disposition"] == (
        'attachment; filename="technical-brief-0.1.0.zip"'
    )


@pytest.mark.asyncio
async def test_proposal_release_integrity_exposes_trusted_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _proposal_release()
    version_id = UUID("019914b2-1a40-7000-8000-000000000101")
    release_id = UUID("019914b2-1a40-7000-8000-000000000102")
    signer = Ed25519ArtifactSigner.from_private_key_bytes("test-key", b"k" * 32)
    signature = signer.sign(
        version_id,
        prepared.package.artifact.integrity.digest,
        signed_at=datetime(2026, 9, 18, tzinfo=UTC),
    )
    trust_store = InMemoryTrustStore(
        [TrustedSigningKey(key_id="test-key", public_key=signer.public_key_bytes())]
    )

    async def resolved(*_args: object):
        return (
            SimpleNamespace(id=release_id, signature=signature.model_dump(mode="json")),
            SimpleNamespace(id=version_id, version="0.1.0"),
            SimpleNamespace(slug="technical-brief"),
            prepared.package.files,
            prepared,
        )

    monkeypatch.setattr(releases, "_proposal_release", resolved)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(artifact_trust_store=trust_store))
    )
    proof = await releases.verify_proposal_release("technical-brief", "0.1.0", request)

    assert proof.release_id == release_id
    assert proof.archive_digest == prepared.archive_digest
    assert proof.content.digest == prepared.package.artifact.integrity.digest
    assert proof.signature.key_id == "test-key"


@pytest.mark.asyncio
async def test_proposal_release_integrity_fails_closed_without_trust_store() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(Exception) as captured:
        await releases.verify_proposal_release("technical-brief", "0.1.0", request)

    assert getattr(captured.value, "status_code", None) == 503


@pytest.mark.asyncio
async def test_proposal_release_integrity_rejects_untrusted_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _proposal_release()
    signer = Ed25519ArtifactSigner.from_private_key_bytes("unknown-key", b"u" * 32)
    version_id = UUID(int=11)
    signature = signer.sign(
        version_id,
        prepared.package.artifact.integrity.digest,
        signed_at=datetime(2026, 9, 18, tzinfo=UTC),
    )

    async def resolved(*_args: object):
        return (
            SimpleNamespace(id=UUID(int=12), signature=signature.model_dump(mode="json")),
            SimpleNamespace(id=version_id, version="0.1.0"),
            SimpleNamespace(slug="technical-brief"),
            prepared.package.files,
            prepared,
        )

    monkeypatch.setattr(releases, "_proposal_release", resolved)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(artifact_trust_store=InMemoryTrustStore()))
    )

    with pytest.raises(Exception) as captured:
        await releases.verify_proposal_release("technical-brief", "0.1.0", request)

    assert getattr(captured.value, "status_code", None) == 503


class _Result:
    def __init__(self, *, row: object | None = None, values: list[object] | None = None) -> None:
        self.row = row
        self.values = values or []

    def first(self) -> object | None:
        return self.row

    def scalars(self) -> Self:
        return self

    def all(self) -> list[object]:
        return self.values


class _Session:
    def __init__(self, results: list[_Result]) -> None:
        self.results = results

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> _Result:
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_proposal_release_is_rebuilt_from_merged_catalog_rows() -> None:
    prepared = _proposal_release()
    version_id = UUID("019914b2-1a40-7000-8000-000000000101")
    package = ProposalPackage(
        files=[
            ProposalFile(
                path=item.path,
                kind=item.kind,
                contentBase64=base64.b64encode(
                    prepared.manifest_bytes
                    if item.path == "artifact.manifest.json"
                    else b"# Technical Brief\n"
                ).decode(),
            )
            for item in prepared.package.files
        ]
    )
    release = SimpleNamespace(id=UUID(int=2), signature={})
    version = SimpleNamespace(
        id=version_id,
        version="0.1.0",
        source_repository="https://github.com/kya/platform",
        source_commit="a" * 40,
        source_path="catalog/templates/skill/technical-brief",
    )
    artifact = SimpleNamespace(slug="technical-brief", artifact_type="skill")
    proposal = SimpleNamespace(package=package.model_dump(mode="json", by_alias=True))
    session = _Session(
        [
            _Result(row=(release, version, artifact, proposal)),
            _Result(values=list(prepared.package.files)),
        ]
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(catalog_sessions=lambda: session))
    )

    resolved = await releases._proposal_release(request, "technical-brief", "0.1.0")

    assert resolved[:4] == (release, version, artifact, list(prepared.package.files))
    assert resolved[4].archive_digest == prepared.archive_digest


@pytest.mark.asyncio
async def test_proposal_release_fails_closed_when_catalog_is_unavailable() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(Exception) as captured:
        await releases._proposal_release(request, "technical-brief", "0.1.0")

    assert getattr(captured.value, "status_code", None) == 503


@pytest.mark.asyncio
async def test_proposal_release_does_not_disclose_unknown_catalog_row() -> None:
    session = _Session([_Result(row=None)])
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(catalog_sessions=lambda: session))
    )

    with pytest.raises(Exception) as captured:
        await releases._proposal_release(request, "unknown", "0.1.0")

    assert getattr(captured.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_proposal_release_rejects_invalid_merged_package() -> None:
    version = SimpleNamespace(
        id=UUID(int=1),
        version="0.1.0",
        source_repository="https://github.com/kya/platform",
        source_commit="a" * 40,
        source_path="catalog/templates/skill/broken",
    )
    row = (
        SimpleNamespace(id=UUID(int=2), signature={}),
        version,
        SimpleNamespace(slug="broken", artifact_type="skill"),
        SimpleNamespace(package={"schemaVersion": "1", "files": []}),
    )
    session = _Session([_Result(row=row), _Result(values=[])])
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(catalog_sessions=lambda: session))
    )

    with pytest.raises(Exception) as captured:
        await releases._proposal_release(request, "broken", "0.1.0")

    assert getattr(captured.value, "status_code", None) == 503
