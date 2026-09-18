"""Deterministic JSON Schema exporter for downstream generators."""

import json
from pathlib import Path

from kya_platform.contracts.artifact_manifest import ArtifactManifest
from kya_platform.contracts.events import KyaEventEnvelope
from kya_platform.contracts.record_schema import RecordSchema


def export_contracts(output_directory: Path) -> list[Path]:
    """Write public schemas and return the generated paths."""

    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / "artifact-manifest.schema.json"
    manifest_path.write_text(
        json.dumps(ArtifactManifest.model_json_schema(by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    event_path = output_directory / "event-envelope.schema.json"
    event_path.write_text(
        json.dumps(KyaEventEnvelope.model_json_schema(by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    record_schema_path = output_directory / "record-schema.schema.json"
    record_schema_path.write_text(
        json.dumps(RecordSchema.model_json_schema(by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    return [manifest_path, event_path, record_schema_path]


__all__ = ["export_contracts"]
