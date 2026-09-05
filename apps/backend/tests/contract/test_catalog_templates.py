"""Official templates remain complete, valid and secret-safe."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kya_platform.contracts import ArtifactManifest

ROOT = Path(__file__).parents[4]
TEMPLATES = ROOT / "catalog" / "templates"


def collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key).lower() for key in value)
        for nested in value.values():
            keys.update(collect_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(collect_keys(nested))
    return keys


@pytest.mark.contract
@pytest.mark.parametrize(
    ("template", "required_file"),
    [
        ("skill/kya-business-method", "SKILL.md"),
        ("mcp-server/kya-capability-mcp", "src/kya_capability_mcp/server.py"),
        ("application/kya-tanstack-app", "src/product-boundary.ts"),
        ("connector/kya-source-connector", "src/kya_source_connector/port.py"),
    ],
)
def test_template_has_valid_manifest_and_implementation_boundary(
    template: str, required_file: str
) -> None:
    directory = TEMPLATES / template
    manifest = ArtifactManifest.model_validate_json(
        (directory / "artifact.manifest.json").read_text(encoding="utf-8")
    )

    assert manifest.version == "0.1.0"
    assert (directory / required_file).is_file()


@pytest.mark.contract
def test_template_manifests_never_define_secret_values() -> None:
    forbidden_keys = {"secret", "password", "token", "api_key", "private_key"}

    for path in TEMPLATES.glob("**/artifact.manifest.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert collect_keys(document).isdisjoint(forbidden_keys), path


@pytest.mark.contract
def test_reference_skill_release_matches_immutable_git_source() -> None:
    release_directory = ROOT / "catalog" / "releases" / "kya-business-method" / "0.1.0"
    manifest = ArtifactManifest.model_validate_json(
        (release_directory / "artifact.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.source.path is not None
    git = shutil.which("git")
    assert git is not None
    source = subprocess.run(  # noqa: S603 - fixed executable and repository-owned manifest
        [git, "show", f"{manifest.source.commit}:{manifest.source.path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout

    assert hashlib.sha256(source).hexdigest() == manifest.integrity.digest
    evidence = json.loads((release_directory / "release-evidence.json").read_text("utf-8"))
    assert evidence["status"] == "published"
    assert len(set(evidence["executionPersonas"].values())) == 4
