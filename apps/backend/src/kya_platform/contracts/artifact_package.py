"""Portable, non-executing package contract for governed KYA artifacts."""

import hashlib
import json
import unicodedata
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kya_platform.contracts.artifact_manifest import ArtifactManifest, ArtifactType

MAX_PACKAGE_FILES = 2_000
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
SHA256_PATTERN = r"^[a-fA-F0-9]{64}$"
REFERENCE_URI_PATTERN = r"^[a-z][a-z0-9-]*://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$"


class StrictPackageContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PackageFileKind(StrEnum):
    INSTRUCTION = "instruction"
    METADATA = "metadata"
    REFERENCE = "reference"
    TEMPLATE = "template"
    SCHEMA = "schema"
    SCRIPT = "script"
    TEST = "test"
    ASSET = "asset"
    MANIFEST = "manifest"


class PackageFile(StrictPackageContract):
    path: str = Field(min_length=1, max_length=512)
    media_type: str = Field(alias="mediaType", min_length=3, max_length=255)
    size: int = Field(ge=0, le=MAX_PACKAGE_BYTES)
    sha256: str = Field(pattern=SHA256_PATTERN)
    kind: PackageFileKind
    executable: bool = False

    @field_validator("path")
    @classmethod
    def validate_portable_path(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFC", value)
        path = PurePosixPath(normalized)
        if normalized != value:
            raise ValueError("package paths must be NFC-normalized")
        if "\\" in value or "\x00" in value or path.is_absolute():
            raise ValueError("package paths must be relative POSIX paths")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("package paths cannot contain empty, dot or parent segments")
        if value.endswith("/"):
            raise ValueError("package entries must identify files")
        return value


class NetworkAccess(StrictPackageContract):
    mode: Literal["none", "allowlist"] = "none"
    allowed_hosts: list[str] = Field(default_factory=list, alias="allowedHosts", max_length=100)

    @model_validator(mode="after")
    def validate_allowlist(self) -> Self:
        if self.mode == "none" and self.allowed_hosts:
            raise ValueError("network hosts require allowlist mode")
        if self.mode == "allowlist" and not self.allowed_hosts:
            raise ValueError("allowlist mode requires at least one host")
        if len(self.allowed_hosts) != len({host.casefold() for host in self.allowed_hosts}):
            raise ValueError("network hosts must be unique")
        return self


class FilesystemAccess(StrictPackageContract):
    read_paths: list[str] = Field(default_factory=list, alias="readPaths", max_length=100)
    write_paths: list[str] = Field(default_factory=list, alias="writePaths", max_length=100)


class ResourceLimits(StrictPackageContract):
    timeout_seconds: int = Field(default=60, alias="timeoutSeconds", ge=1, le=3_600)
    memory_megabytes: int = Field(default=512, alias="memoryMegabytes", ge=64, le=8_192)


class CapabilityManifest(StrictPackageContract):
    """Requested execution envelope; it never grants a capability by itself."""

    schema_version: Literal["1"] = Field(alias="schemaVersion")
    runtime: str = Field(min_length=1, max_length=100)
    entrypoints: dict[str, str] = Field(min_length=1, max_length=50)
    commands: list[str] = Field(default_factory=list, max_length=50)
    network: NetworkAccess = Field(default_factory=NetworkAccess)
    filesystem: FilesystemAccess = Field(default_factory=FilesystemAccess)
    secret_references: list[str] = Field(default_factory=list, alias="secretReferences")
    requested_permissions: list[str] = Field(default_factory=list, alias="requestedPermissions")
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits, alias="resourceLimits")

    @field_validator("secret_references")
    @classmethod
    def validate_secret_references(cls, values: list[str]) -> list[str]:
        import re

        if len(values) != len(set(values)):
            raise ValueError("secret references must be unique")
        if any(re.fullmatch(REFERENCE_URI_PATTERN, value) is None for value in values):
            raise ValueError("secret references must be provider URIs, never values")
        return values

    @field_validator("requested_permissions")
    @classmethod
    def validate_unique_permissions(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("requested permissions must be unique")
        return values


class ArtifactPackage(StrictPackageContract):
    """Manifest plus canonical file inventory, validated without executing content."""

    schema_version: Literal["1"] = Field(alias="schemaVersion")
    artifact: ArtifactManifest
    files: Annotated[list[PackageFile], Field(min_length=1, max_length=MAX_PACKAGE_FILES)]
    capability: CapabilityManifest | None = None

    @model_validator(mode="after")
    def validate_package(self) -> Self:
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("package file paths must be unique")
        if len(paths) != len({path.casefold() for path in paths}):
            raise ValueError("package file paths cannot differ only by case")
        if sum(item.size for item in self.files) > MAX_PACKAGE_BYTES:
            raise ValueError("package exceeds maximum uncompressed size")

        by_path = {item.path: item for item in self.files}
        if "artifact.manifest.json" not in by_path:
            raise ValueError("artifact.manifest.json must be inventoried")
        if self.artifact.artifact_type is ArtifactType.SKILL:
            skill = by_path.get("SKILL.md")
            if skill is None or skill.kind is not PackageFileKind.INSTRUCTION:
                raise ValueError("a skill requires SKILL.md classified as instruction")
            if skill.executable:
                raise ValueError("SKILL.md cannot be executable")

        has_executable_content = any(
            item.executable or item.kind is PackageFileKind.SCRIPT for item in self.files
        )
        if has_executable_content and self.capability is None:
            raise ValueError("executable content requires a capability manifest")
        if self.capability is not None and "capability.manifest.json" not in by_path:
            raise ValueError("capability manifest must be inventoried")
        return self

    @property
    def has_executable_content(self) -> bool:
        return any(item.executable or item.kind is PackageFileKind.SCRIPT for item in self.files)

    def inventory_digest(self) -> str:
        """Hash a stable inventory representation independent of JSON formatting."""

        inventory = [
            {
                "executable": item.executable,
                "kind": item.kind.value,
                "mediaType": item.media_type,
                "path": item.path,
                "sha256": item.sha256.lower(),
                "size": item.size,
            }
            for item in sorted(self.files, key=lambda candidate: candidate.path)
        ]
        payload = json.dumps(inventory, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


def canonical_content_payload(files: list[PackageFile]) -> bytes:
    """Serialize the v1 content inventory, excluding its self-referential manifest."""

    inventory = [
        {"path": item.path, "sha256": item.sha256.lower(), "size": item.size}
        for item in sorted(files, key=lambda candidate: candidate.path)
        if item.path != "artifact.manifest.json"
    ]
    return json.dumps(inventory, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


__all__ = [
    "MAX_PACKAGE_BYTES",
    "MAX_PACKAGE_FILES",
    "ArtifactPackage",
    "CapabilityManifest",
    "FilesystemAccess",
    "NetworkAccess",
    "PackageFile",
    "PackageFileKind",
    "ResourceLimits",
    "canonical_content_payload",
]
