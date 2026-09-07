"""Security tests for real multi-file artifact archive ingestion."""

import hashlib
import io
import json
import stat
import zipfile
from collections.abc import Mapping

import pytest

from kya_platform.application.artifact_registry.archive import (
    ArchiveValidationError,
    ArtifactArchiveValidator,
)


def _digest(files: Mapping[str, bytes]) -> str:
    inventory = [
        {"path": path, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        for path, content in sorted(files.items())
    ]
    canonical = json.dumps(inventory, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _archive(*, executable: bool = False, overrides: Mapping[str, bytes] | None = None) -> bytes:
    files: dict[str, bytes] = {
        "SKILL.md": (
            b"---\nname: document-standard\n"
            b"description: Genere les documents conformes KYA.\n---\n\n# Instructions\n"
        ),
        "references/charte.md": b"# Charte KYA\n",
    }
    capability = None
    if executable:
        files.update(
            {
                "scripts/render.py": b"def render():\n    return 'ok'\n",
                "tests/test_render.py": b"def test_render():\n    assert True\n",
                "sbom.cdx.json": b'{"bomFormat":"CycloneDX","specVersion":"1.6"}',
            }
        )
        capability = {
            "schemaVersion": "1",
            "runtime": "python>=3.14",
            "entrypoints": {"render": "scripts/render.py"},
            "network": {"mode": "none"},
            "secretReferences": [],
            "requestedPermissions": ["document.render"],
        }
        files["capability.manifest.json"] = json.dumps(capability).encode()
    if overrides:
        files.update(overrides)
    manifest = {
        "schemaVersion": "1",
        "id": "kya:skill:document-standard",
        "type": "skill",
        "name": "Standard documentaire KYA",
        "version": "1.0.0",
        "owners": {
            "business": "communication",
            "technical": "cvsi-platform",
            "workspace": "communication",
        },
        "source": {
            "repository": "https://github.com/kya-energy/document-standard",
            "commit": "a" * 40,
        },
        "integrity": {"algorithm": "sha256", "digest": _digest(files)},
        "compatibility": {"codex": ">=2026-09"},
        "risk": "controlled-write" if executable else "read",
    }
    files["artifact.manifest.json"] = json.dumps(manifest).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path, content in files.items():
            zipped.writestr(path, content)
    return stream.getvalue()


def test_validates_declarative_skill_content_without_execution() -> None:
    result = ArtifactArchiveValidator().validate(_archive())

    assert result.package.artifact.artifact_id == "kya:skill:document-standard"
    assert result.package.has_executable_content is False
    assert len(result.archive_digest) == 64


def test_validates_python_skill_with_capability_tests_and_sbom() -> None:
    result = ArtifactArchiveValidator().validate(_archive(executable=True))

    assert result.package.has_executable_content is True
    assert result.package.capability is not None
    assert result.package.capability.entrypoints == {"render": "scripts/render.py"}


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "folder/../secret.txt"])
def test_rejects_path_traversal(path: str) -> None:
    with pytest.raises(ArchiveValidationError, match="unsafe package path"):
        ArtifactArchiveValidator().validate(_archive(overrides={path: b"secret"}))


def test_rejects_case_ambiguous_archive() -> None:
    with pytest.raises(ArchiveValidationError, match="differ only by case"):
        ArtifactArchiveValidator().validate(_archive(overrides={"skill.md": b"duplicate"}))


def test_rejects_probable_secret_value() -> None:
    with pytest.raises(ArchiveValidationError, match="probable secret"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"references/config.txt": b"API_KEY=abcdefghijklmnop123456"})
        )


def test_rejects_python_skill_without_declared_capability() -> None:
    with pytest.raises(ArchiveValidationError, match="capability manifest"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"scripts/undeclared.py": b"print('never executed')\n"})
        )


def test_rejects_manifest_digest_mismatch() -> None:
    archive = _archive()
    source = io.BytesIO(archive)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as changed,
    ):
        for item in original.infolist():
            content = original.read(item)
            if item.filename == "references/charte.md":
                content = b"modified after manifest\n"
            changed.writestr(item.filename, content)

    with pytest.raises(ArchiveValidationError, match="digest does not match"):
        ArtifactArchiveValidator().validate(output.getvalue())


def test_rejects_symbolic_link_without_following_it() -> None:
    source = io.BytesIO(_archive())
    output = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as changed:
        for item in original.infolist():
            changed.writestr(item, original.read(item))
        link = zipfile.ZipInfo("references/outside-link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        changed.writestr(link, "../../outside")

    with pytest.raises(ArchiveValidationError, match="symbolic links are forbidden"):
        ArtifactArchiveValidator().validate(output.getvalue())


def test_rejects_native_executable() -> None:
    with pytest.raises(ArchiveValidationError, match="native executable is not portable"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"assets/untrusted.exe": b"MZ" + b"0" * 100})
        )


def test_rejects_suspicious_compression_ratio() -> None:
    with pytest.raises(ArchiveValidationError, match="suspicious compression ratio"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"assets/compressed.bin": b"0" * (1024 * 1024 + 1)})
        )


def test_rejects_skill_without_required_frontmatter() -> None:
    with pytest.raises(ArchiveValidationError, match="frontmatter"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"SKILL.md": b"# Missing frontmatter\n"})
        )


def test_rejects_empty_and_malformed_archives() -> None:
    validator = ArtifactArchiveValidator()

    with pytest.raises(ArchiveValidationError, match="archive size"):
        validator.validate(b"")
    with pytest.raises(ArchiveValidationError, match="valid ZIP"):
        validator.validate(b"not-a-zip")


def test_rejects_zip_without_files_or_manifest() -> None:
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w"):
        pass
    with pytest.raises(ArchiveValidationError, match="file count"):
        ArtifactArchiveValidator().validate(empty.getvalue())

    missing = io.BytesIO()
    with zipfile.ZipFile(missing, "w") as archive:
        archive.writestr("SKILL.md", b"---\nname: a\ndescription: b\n---\n")
    with pytest.raises(ArchiveValidationError, match="required file is missing"):
        ArtifactArchiveValidator().validate(missing.getvalue())


def test_rejects_unclosed_or_incomplete_skill_frontmatter() -> None:
    with pytest.raises(ArchiveValidationError, match="not closed"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"SKILL.md": b"---\nname: incomplete\ndescription: present\nbody\n"})
        )
    with pytest.raises(ArchiveValidationError, match="requires name and description"):
        ArtifactArchiveValidator().validate(
            _archive(overrides={"SKILL.md": b"---\nname: incomplete\n---\nbody\n"})
        )


def test_rejects_files_outside_the_portable_layout() -> None:
    with pytest.raises(ArchiveValidationError, match="unsupported package path"):
        ArtifactArchiveValidator().validate(_archive(overrides={"random.txt": b"content"}))


def test_rejects_skill_name_that_differs_from_artifact_slug() -> None:
    skill = b"---\nname: another-skill\ndescription: Mismatch.\n---\nbody\n"
    with pytest.raises(ArchiveValidationError, match="name must match"):
        ArtifactArchiveValidator().validate(_archive(overrides={"SKILL.md": skill}))


def test_rejects_invalid_cyclonedx_sbom() -> None:
    with pytest.raises(ArchiveValidationError, match="CycloneDX"):
        ArtifactArchiveValidator().validate(
            _archive(executable=True, overrides={"sbom.cdx.json": b'{"format":"other"}'})
        )

    with pytest.raises(ArchiveValidationError, match="valid CycloneDX JSON"):
        ArtifactArchiveValidator().validate(
            _archive(executable=True, overrides={"sbom.cdx.json": b"not-json"})
        )
