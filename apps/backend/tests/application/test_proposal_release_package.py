"""Merged proposal packages become deterministic, provenance-bound releases."""

import base64
import hashlib
import io
import json
import zipfile

import pytest

from kya_platform.application.artifact_registry.release_package import prepare_proposal_release
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode()


def proposal_package() -> ProposalPackage:
    manifest = {
        "schemaVersion": "1",
        "id": "kya:skill:technical-brief",
        "type": "skill",
        "name": "Technical Brief",
        "version": "0.1.0",
        "summary": "A governed brief.",
        "owners": {"business": "communication", "technical": "cvsi", "workspace": "team"},
        "compatibility": {"claude-code": ">=2026-09", "codex": ">=2026-09"},
        "dependencies": [],
        "scopes": ["skill.discover"],
        "risk": "read",
    }
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                contentBase64=_encoded(json.dumps(manifest).encode()),
            ),
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                contentBase64=_encoded(b"---\nname: technical-brief\n---\n"),
            ),
        ]
    )


def test_release_is_deterministic_and_binds_server_owned_provenance() -> None:
    arguments = {
        "proposal_package": proposal_package(),
        "slug": "technical-brief",
        "artifact_type": ArtifactType.SKILL,
        "source_repository": "https://github.com/kya/platform",
        "source_commit": "a" * 40,
        "source_path": "catalog/sources/skills/technical-brief",
    }

    first = prepare_proposal_release(**arguments)
    second = prepare_proposal_release(**arguments)

    assert first.archive == second.archive
    assert first.archive_digest == hashlib.sha256(first.archive).hexdigest()
    assert first.package.artifact.source.commit == "a" * 40
    assert first.package.artifact.integrity.digest
    with zipfile.ZipFile(io.BytesIO(first.archive)) as archive:
        manifest = json.loads(archive.read("artifact.manifest.json"))
        assert manifest["source"]["commit"] == "a" * 40
        assert manifest["integrity"]["digest"] == first.package.artifact.integrity.digest


def test_release_rejects_a_manifest_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="identity"):
        prepare_proposal_release(
            proposal_package=proposal_package(),
            slug="another-skill",
            artifact_type=ArtifactType.SKILL,
            source_repository="https://github.com/kya/platform",
            source_commit="a" * 40,
            source_path="catalog/sources/skills/another-skill",
        )
