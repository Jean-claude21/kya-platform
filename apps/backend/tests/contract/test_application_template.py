"""The official application template stays autonomous and governed."""

import json
from pathlib import Path

from kya_platform.contracts.artifact_manifest import ArtifactManifest

ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / "catalog" / "templates" / "application" / "kya-tanstack-app"


def test_template_contains_runtime_delivery_and_governance_boundaries() -> None:
    required = {
        ".env.example",
        ".github/workflows/ci.yml",
        ".npmrc.example",
        "Dockerfile",
        "README.md",
        "artifact.manifest.json",
        "nginx.conf",
        "package.json",
        "src/product-boundary.ts",
    }

    assert required <= {
        str(path.relative_to(TEMPLATE)).replace("\\", "/")
        for path in TEMPLATE.rglob("*")
        if path.is_file()
    }


def test_template_manifest_requires_the_current_sdk_contract() -> None:
    payload = json.loads((TEMPLATE / "artifact.manifest.json").read_text(encoding="utf-8"))

    manifest = ArtifactManifest.model_validate(payload)

    assert manifest.application is not None
    assert manifest.application.required_sdk == ">=0.2.0"
    assert manifest.governance is not None


def test_template_never_contains_a_secret_value() -> None:
    public_files = (
        TEMPLATE / ".env.example",
        TEMPLATE / ".npmrc.example",
        TEMPLATE / "infisical.example.json",
    )

    content = "\n".join(path.read_text(encoding="utf-8") for path in public_files)

    assert "client_secret" not in content.casefold()
    assert "password=" not in content.casefold()
    assert "${GITHUB_PACKAGES_TOKEN}" in content
