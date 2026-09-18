"""Public artifact manifest contract tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from kya_platform.contracts.artifact_manifest import ArtifactManifest
from kya_platform.contracts.export import export_contracts


def valid_manifest() -> dict[str, object]:
    return {
        "schemaVersion": "1",
        "id": "kya:skill:communication-document",
        "type": "skill",
        "name": "Communication Document",
        "version": "1.2.0-dev.1",
        "summary": "Applique les règles documentaires validées par la Communication.",
        "owners": {
            "business": "direction-communication",
            "technical": "cvsi",
            "workspace": "communication",
        },
        "source": {
            "repository": "https://github.com/kya-energy/communication-document",
            "commit": "a" * 40,
            "path": "skill/",
        },
        "integrity": {"algorithm": "sha256", "digest": "b" * 64},
        "compatibility": {"codex": ">=1", "claude-code": ">=1"},
        "dependencies": [],
        "scopes": ["catalog:read"],
        "risk": "read",
    }


@pytest.mark.contract
def test_accepts_a_complete_manifest() -> None:
    manifest = ArtifactManifest.model_validate(valid_manifest())

    assert manifest.schema_version == "1"
    assert manifest.artifact_id == "kya:skill:communication-document"
    assert manifest.model_dump(mode="json", by_alias=True)["schemaVersion"] == "1"


@pytest.mark.contract
@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    [
        (("id",), "skill-without-kya-prefix"),
        (("version",), "latest"),
        (("source", "commit"), "abc123"),
        (("integrity", "algorithm"), "md5"),
        (("integrity", "digest"), "too-short"),
    ],
)
def test_rejects_invalid_identity_and_integrity(
    field_path: tuple[str, ...], invalid_value: str
) -> None:
    payload = valid_manifest()
    target = payload
    for field in field_path[:-1]:
        target = target[field]  # type: ignore[assignment,index]
    target[field_path[-1]] = invalid_value  # type: ignore[index]

    with pytest.raises(ValidationError):
        ArtifactManifest.model_validate(payload)


@pytest.mark.contract
def test_rejects_unknown_fields() -> None:
    payload = valid_manifest()
    payload["secretValue"] = "must-never-enter-the-catalog"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ArtifactManifest.model_validate(payload)


@pytest.mark.contract
def test_rejects_duplicate_scopes() -> None:
    payload = valid_manifest()
    payload["scopes"] = ["catalog:read", "catalog:read"]

    with pytest.raises(ValidationError, match="Scopes must be unique"):
        ArtifactManifest.model_validate(payload)


@pytest.mark.contract
def test_accepts_governed_application_launch_metadata() -> None:
    payload = valid_manifest()
    payload.update(
        {
            "id": "kya:app:kya-forms",
            "type": "app",
            "governance": {
                "visibility": "restricted",
                "defaultScope": "workspace",
                "allowedScopes": ["workspace", "unit", "group"],
                "permissions": ["view", "use", "create", "edit", "administer"],
            },
            "features": [
                {
                    "key": "forms.builder",
                    "name": "Form builder",
                    "permissions": ["view", "create", "edit"],
                }
            ],
            "application": {
                "launch": {
                    "url": "https://forms.kya.example",
                    "mode": "same-tab",
                    "iconUrl": "https://forms.kya.example/icon.svg",
                    "healthUrl": "https://forms.kya.example/health",
                },
                "requiredSdk": ">=0.2.0",
            },
            "integrations": {
                "apiBaseUrl": "https://forms.kya.example/api",
                "emits": ["form.submitted"],
                "consumes": [],
                "webhooks": ["form.submitted"],
                "mcpTools": ["forms.create_form"],
            },
        }
    )

    manifest = ArtifactManifest.model_validate(payload)

    assert manifest.application is not None
    assert str(manifest.application.launch.url) == "https://forms.kya.example/"
    assert manifest.governance is not None
    assert manifest.governance.default_scope.value == "workspace"


@pytest.mark.contract
def test_rejects_application_metadata_on_non_app_artifact() -> None:
    payload = valid_manifest()
    payload["application"] = {"launch": {"url": "https://forms.kya.example"}}

    with pytest.raises(ValidationError, match="Only app artifacts"):
        ArtifactManifest.model_validate(payload)


@pytest.mark.contract
def test_rejects_default_scope_outside_allowed_scopes() -> None:
    payload = valid_manifest()
    payload["governance"] = {
        "defaultScope": "workspace",
        "allowedScopes": ["unit"],
        "permissions": ["view"],
    }

    with pytest.raises(ValidationError, match="default scope"):
        ArtifactManifest.model_validate(payload)


@pytest.mark.contract
def test_exports_a_versioned_json_schema(tmp_path: Path) -> None:
    generated_paths = export_contracts(tmp_path)

    assert generated_paths == [
        tmp_path / "artifact-manifest.schema.json",
        tmp_path / "event-envelope.schema.json",
        tmp_path / "record-schema.schema.json",
    ]
    schema = json.loads(generated_paths[0].read_text(encoding="utf-8"))
    assert schema["$id"] == "https://schemas.kya.energy/platform/artifact-manifest/v1"
    assert schema["properties"]["schemaVersion"]["const"] == "1"
