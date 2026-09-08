"""Vendor-neutral primitives for governed data acquisition and delivery."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _required_key(value: str, name: str) -> None:
    if _KEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be a stable kebab-case identifier")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def _public_configuration(value: object) -> None:
    forbidden = {"secret", "password", "token", "credential", "api_key", "access_key"}
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(marker in normalized for marker in forbidden):
                raise ValueError("source configuration must not contain credential fields")
            _public_configuration(nested)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for nested in value:
            _public_configuration(nested)
    elif value is not None and not isinstance(value, str | int | float | bool):
        raise ValueError("source configuration must contain JSON values only")


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataAssetLayer(StrEnum):
    RAW = "raw"
    STANDARDIZED = "standardized"
    CURATED = "curated"
    PRODUCT = "product"


class DataStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DataSourceKind(StrEnum):
    WEB = "web"
    API = "api"
    DATABASE = "database"
    FILE = "file"
    STREAM = "stream"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class DataSource:
    id: UUID
    key: str
    name: str
    kind: DataSourceKind
    owner_unit_id: UUID
    system_artifact_id: UUID | None = None
    secret_reference: str | None = None
    status: DataStatus = DataStatus.DRAFT
    configuration: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_key(self.key, "data source key")
        if not self.name.strip():
            raise ValueError("data source name is required")
        if self.secret_reference is not None:
            if not self.secret_reference.strip() or "://" in self.secret_reference:
                raise ValueError("secret_reference must be an opaque reference, not a URL")
        _public_configuration(self.configuration)


@dataclass(frozen=True, slots=True)
class DataAsset:
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    layer: DataAssetLayer
    classification: DataClassification
    status: DataStatus = DataStatus.DRAFT

    def __post_init__(self) -> None:
        _required_key(self.key, "data asset key")
        if not self.name.strip():
            raise ValueError("data asset name is required")


@dataclass(frozen=True, slots=True)
class QualityRule:
    key: str
    kind: str
    expression: str
    severity: str = "error"

    def __post_init__(self) -> None:
        _required_key(self.key, "quality rule key")
        if not self.kind.strip() or not self.expression.strip():
            raise ValueError("quality rule kind and expression are required")
        if self.severity not in {"warning", "error"}:
            raise ValueError("quality rule severity must be warning or error")


@dataclass(frozen=True, slots=True)
class DataContract:
    id: UUID
    asset_id: UUID
    version: str
    schema: dict[str, object]
    digest: str
    quality_rules: tuple[QualityRule, ...] = ()
    freshness_minutes: int | None = None
    retention_days: int | None = None

    def __post_init__(self) -> None:
        if _SEMVER.fullmatch(self.version) is None:
            raise ValueError("data contract version must follow SemVer")
        if not self.schema:
            raise ValueError("data contract schema is required")
        if _SHA256.fullmatch(self.digest) is None:
            raise ValueError("data contract digest must be a lowercase SHA-256 digest")
        if self.freshness_minutes is not None and self.freshness_minutes < 1:
            raise ValueError("freshness must be positive")
        if self.retention_days is not None and self.retention_days < 1:
            raise ValueError("retention must be positive")
        rule_keys = [rule.key for rule in self.quality_rules]
        if len(rule_keys) != len(set(rule_keys)):
            raise ValueError("quality rule keys must be unique")


@dataclass(frozen=True, slots=True)
class DataPipeline:
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    source_id: UUID
    connector_version_id: UUID
    output_asset_id: UUID
    status: DataStatus = DataStatus.DRAFT

    def __post_init__(self) -> None:
        _required_key(self.key, "data pipeline key")
        if not self.name.strip():
            raise ValueError("data pipeline name is required")


class RunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class QualityStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class QualityResult:
    rule_key: str
    status: QualityStatus
    observed: dict[str, object] | None = None

    def __post_init__(self) -> None:
        _required_key(self.rule_key, "quality result rule key")


@dataclass(frozen=True, slots=True)
class IngestionRun:
    id: UUID
    pipeline_id: UUID
    triggered_by: UUID
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        _aware(self.started_at, "started_at")
        if self.completed_at is not None:
            _aware(self.completed_at, "completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot precede started_at")
        if self.status is RunStatus.STARTED and self.completed_at is not None:
            raise ValueError("a started run cannot have completed_at")
        if self.status is not RunStatus.STARTED and self.completed_at is None:
            raise ValueError("a terminal run requires completed_at")
        if self.status is RunStatus.FAILED and not self.error_code:
            raise ValueError("a failed run requires a stable error code")

    def complete(self, completed_at: datetime) -> IngestionRun:
        if self.status is not RunStatus.STARTED:
            raise ValueError("only a started run can complete")
        return replace(self, status=RunStatus.COMPLETED, completed_at=completed_at)

    def fail(self, completed_at: datetime, error_code: str) -> IngestionRun:
        if self.status is not RunStatus.STARTED:
            raise ValueError("only a started run can fail")
        return replace(
            self,
            status=RunStatus.FAILED,
            completed_at=completed_at,
            error_code=error_code,
        )


@dataclass(frozen=True, slots=True)
class StorageObject:
    provider: str
    container: str
    object_key: str
    version_id: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.container.strip() or not self.object_key.strip():
            raise ValueError("storage provider, container and object key are required")
        if "://" in self.object_key or "?" in self.object_key:
            raise ValueError("storage object key must not contain a URL or signed query")


@dataclass(frozen=True, slots=True)
class DataSnapshot:
    id: UUID
    asset_id: UUID
    run_id: UUID
    contract_id: UUID
    storage: StorageObject
    content_digest: str
    media_type: str
    observed_at: datetime
    row_count: int | None = None
    byte_size: int | None = None

    def __post_init__(self) -> None:
        _aware(self.observed_at, "observed_at")
        if _SHA256.fullmatch(self.content_digest) is None:
            raise ValueError("snapshot digest must be a lowercase SHA-256 digest")
        if not self.media_type.strip():
            raise ValueError("snapshot media type is required")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row count cannot be negative")
        if self.byte_size is not None and self.byte_size < 0:
            raise ValueError("byte size cannot be negative")


__all__ = [
    "DataAsset",
    "DataAssetLayer",
    "DataClassification",
    "DataContract",
    "DataPipeline",
    "DataSnapshot",
    "DataSource",
    "DataSourceKind",
    "DataStatus",
    "IngestionRun",
    "QualityResult",
    "QualityRule",
    "QualityStatus",
    "RunStatus",
    "StorageObject",
]
