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


def document_type_proposal_package() -> ProposalPackage:
    manifest = {
        "schemaVersion": "1",
        "id": "kya:document-type:employee-survey",
        "type": "document-type",
        "name": "Employee survey",
        "version": "0.1.0",
        "owners": {"business": "people", "technical": "cvsi", "workspace": "people"},
        "compatibility": {"kya-document-runtime": ">=0.1.0"},
        "dependencies": [],
        "scopes": ["document.create"],
        "risk": "controlled-write",
    }
    definition = {
        "schemaVersion": "1",
        "id": "kya:document-type:employee-survey",
        "version": "0.1.0",
        "name": "Employee survey",
        "recordSchema": {
            "schemaVersion": "1",
            "id": "kya:data-schema:employee-survey-response",
            "version": "0.1.0",
            "name": "Employee survey response",
            "ownerScope": "workspace:people",
            "fields": [{"key": "rating", "label": "Rating", "type": "integer"}],
            "access": {"permissions": ["view", "create"]},
            "retention": {"retainDays": 365},
        },
        "workflow": {
            "initialState": "draft",
            "states": [
                {"key": "draft", "name": "Draft", "category": "draft"},
                {
                    "key": "submitted",
                    "name": "Submitted",
                    "category": "completed",
                    "terminal": True,
                },
            ],
            "transitions": [
                {
                    "key": "submit",
                    "name": "Submit",
                    "fromState": "draft",
                    "toState": "submitted",
                    "permission": "create",
                    "actors": [{"kind": "actor", "value": "current"}],
                }
            ],
        },
        "views": [
            {
                "key": "survey_form",
                "name": "Survey form",
                "type": "form",
                "fields": ["rating"],
                "default": True,
            }
        ],
    }
    return ProposalPackage(
        files=[
            ProposalFile(
                path="artifact.manifest.json",
                kind=PackageFileKind.MANIFEST,
                contentBase64=_encoded(json.dumps(manifest).encode()),
            ),
            ProposalFile(
                path="document-type.json",
                kind=PackageFileKind.SCHEMA,
                contentBase64=_encoded(json.dumps(definition).encode()),
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


def test_document_type_release_validates_and_preserves_the_definition() -> None:
    release = prepare_proposal_release(
        proposal_package=document_type_proposal_package(),
        slug="employee-survey",
        artifact_type=ArtifactType.DOCUMENT_TYPE,
        source_repository="https://github.com/kya/platform",
        source_commit="b" * 40,
        source_path="catalog/sources/document-types/employee-survey",
    )

    assert release.package.artifact.artifact_type.value == "document-type"
    with zipfile.ZipFile(io.BytesIO(release.archive)) as archive:
        definition = json.loads(archive.read("document-type.json"))
        assert definition["id"] == "kya:document-type:employee-survey"


def test_document_type_release_rejects_definition_version_mismatch() -> None:
    package = document_type_proposal_package()
    definition = json.loads(package.files[1].decoded())
    definition["version"] = "0.2.0"
    package.files[1].content_base64 = _encoded(json.dumps(definition).encode())

    with pytest.raises(ValueError, match="version does not match"):
        prepare_proposal_release(
            proposal_package=package,
            slug="employee-survey",
            artifact_type=ArtifactType.DOCUMENT_TYPE,
            source_repository="https://github.com/kya/platform",
            source_commit="b" * 40,
            source_path="catalog/sources/document-types/employee-survey",
        )
