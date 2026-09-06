"""Contract tests for portable multi-file KYA artifact packages."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from kya_platform.contracts.artifact_package import ArtifactPackage

DIGEST = "a" * 64
COMMIT = "b" * 40


def package_payload(*, executable: bool = False) -> dict[str, object]:
    files: list[dict[str, object]] = [
        {
            "path": "artifact.manifest.json",
            "mediaType": "application/json",
            "size": 700,
            "sha256": DIGEST,
            "kind": "manifest",
        },
        {
            "path": "SKILL.md",
            "mediaType": "text/markdown",
            "size": 900,
            "sha256": "c" * 64,
            "kind": "instruction",
        },
    ]
    capability = None
    if executable:
        files.extend(
            [
                {
                    "path": "capability.manifest.json",
                    "mediaType": "application/json",
                    "size": 500,
                    "sha256": "d" * 64,
                    "kind": "manifest",
                },
                {
                    "path": "scripts/render.py",
                    "mediaType": "text/x-python",
                    "size": 1200,
                    "sha256": "e" * 64,
                    "kind": "script",
                    "executable": True,
                },
            ]
        )
        capability = {
            "schemaVersion": "1",
            "runtime": "python>=3.12",
            "entrypoints": {"render": "scripts/render.py"},
            "network": {"mode": "none"},
            "filesystem": {"readPaths": ["inputs/"], "writePaths": ["outputs/"]},
            "secretReferences": ["infisical://skills/document-renderer/api-key"],
            "requestedPermissions": ["document.render"],
        }
    return {
        "schemaVersion": "1",
        "artifact": {
            "schemaVersion": "1",
            "id": "kya:skill:document-renderer",
            "type": "skill",
            "name": "Document Renderer",
            "version": "1.0.0",
            "owners": {
                "business": "communication",
                "technical": "cvsi-platform",
                "workspace": "communication",
            },
            "source": {
                "repository": "https://github.com/kya-energy/document-renderer",
                "commit": COMMIT,
                "path": "skills/document-renderer",
            },
            "integrity": {"algorithm": "sha256", "digest": DIGEST},
            "compatibility": {"codex": ">=2026-09", "claude-code": ">=2"},
            "scopes": ["skill.discover"],
            "risk": "controlled-write" if executable else "read",
        },
        "files": files,
        "capability": capability,
    }


def test_accepts_declarative_skill() -> None:
    package = ArtifactPackage.model_validate(package_payload())

    assert package.has_executable_content is False
    assert len(package.inventory_digest()) == 64


def test_accepts_executable_skill_with_explicit_capability_envelope() -> None:
    package = ArtifactPackage.model_validate(package_payload(executable=True))

    assert package.has_executable_content is True
    assert package.capability is not None
    assert package.capability.network.mode == "none"


@pytest.mark.parametrize(
    "dangerous_path",
    ["../secret.txt", "/etc/passwd", "scripts\\run.py", "folder/../secret.txt", "file.txt/"],
)
def test_rejects_non_portable_paths(dangerous_path: str) -> None:
    payload = package_payload()
    payload["files"][1]["path"] = dangerous_path  # type: ignore[index]

    with pytest.raises(ValidationError, match=r"package paths|package entries"):
        ArtifactPackage.model_validate(payload)


def test_rejects_case_ambiguous_paths() -> None:
    payload = package_payload()
    payload["files"].append(deepcopy(payload["files"][1]))  # type: ignore[union-attr,index]
    payload["files"][-1]["path"] = "skill.md"  # type: ignore[index]

    with pytest.raises(ValidationError, match="differ only by case"):
        ArtifactPackage.model_validate(payload)


def test_rejects_executable_content_without_capability_manifest() -> None:
    payload = package_payload()
    payload["files"].append(  # type: ignore[union-attr]
        {
            "path": "scripts/run.py",
            "mediaType": "text/x-python",
            "size": 10,
            "sha256": "f" * 64,
            "kind": "script",
            "executable": True,
        }
    )

    with pytest.raises(ValidationError, match="requires a capability manifest"):
        ArtifactPackage.model_validate(payload)


def test_rejects_secret_values_disguised_as_references() -> None:
    payload = package_payload(executable=True)
    payload["capability"]["secretReferences"] = ["plain-api-key"]  # type: ignore[index]

    with pytest.raises(ValidationError, match="provider URIs"):
        ArtifactPackage.model_validate(payload)


def test_inventory_digest_is_independent_of_file_order() -> None:
    first = ArtifactPackage.model_validate(package_payload(executable=True))
    reversed_payload = package_payload(executable=True)
    reversed_payload["files"] = list(reversed(reversed_payload["files"]))  # type: ignore[arg-type]
    second = ArtifactPackage.model_validate(reversed_payload)

    assert first.inventory_digest() == second.inventory_digest()
