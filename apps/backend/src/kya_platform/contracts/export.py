"""Deterministic JSON Schema exporter for downstream generators."""

import json
from pathlib import Path

from kya_platform.contracts.artifact_manifest import ArtifactManifest


def export_contracts(output_directory: Path) -> list[Path]:
    """Write public schemas and return the generated paths."""

    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / "artifact-manifest.schema.json"
    manifest_path.write_text(
        json.dumps(ArtifactManifest.model_json_schema(by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    return [manifest_path]


__all__ = ["export_contracts"]
