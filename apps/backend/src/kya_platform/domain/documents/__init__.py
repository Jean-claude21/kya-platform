"""Native, runtime-neutral business document aggregates."""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_PUBLIC_ID = re.compile(r"^kya:document-type:[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")

type DocumentScalar = str | int | float | bool | None
type DocumentValue = DocumentScalar | Mapping[str, "DocumentValue"] | Sequence["DocumentValue"]


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def _scope(value: str) -> None:
    prefix, separator, identifier = value.partition(":")
    if separator != ":" or prefix not in {"personal", "workspace", "unit", "filiale", "group"}:
        raise ValueError("owner_scope must be a governed KYA scope")
    if not identifier or len(value) > 255:
        raise ValueError("owner_scope must contain a bounded identifier")


def _json_value(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("document objects require string keys")
            _json_value(nested)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for nested in value:
            _json_value(nested)
    elif value is not None and not isinstance(value, str | int | float | bool):
        raise ValueError("document values must be JSON compatible")


def canonical_digest(value: DocumentValue) -> str:
    """Return the stable digest used for immutable definitions and revisions."""

    _json_value(value)
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class EvidenceKind(StrEnum):
    TRANSITION = "transition"
    SIGNATURE = "signature"
    ATTACHMENT = "attachment"
    NOTIFICATION = "notification"


@dataclass(frozen=True, slots=True)
class DocumentDefinition:
    id: UUID
    public_id: str
    version: str
    owner_scope: str
    release_id: UUID
    definition: Mapping[str, DocumentValue]
    digest: str
    published_by: UUID
    published_at: datetime

    def __post_init__(self) -> None:
        if _PUBLIC_ID.fullmatch(self.public_id) is None:
            raise ValueError("public_id must be a KYA document-type identifier")
        if _SEMVER.fullmatch(self.version) is None:
            raise ValueError("document definition version must follow SemVer")
        _scope(self.owner_scope)
        _aware(self.published_at, "published_at")
        _json_value(self.definition)
        if (
            _SHA256.fullmatch(self.digest) is None
            or canonical_digest(self.definition) != self.digest
        ):
            raise ValueError("definition digest must match its canonical JSON")


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: UUID
    definition_id: UUID
    owner_scope: str
    state: str
    current_revision: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _scope(self.owner_scope)
        if not self.state.strip() or len(self.state) > 120:
            raise ValueError("document state is required")
        if self.current_revision < 1:
            raise ValueError("current_revision must be positive")
        _aware(self.created_at, "created_at")
        _aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class DocumentRevision:
    record_id: UUID
    revision: int
    payload: Mapping[str, DocumentValue]
    digest: str
    authored_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("revision must be positive")
        _json_value(self.payload)
        if _SHA256.fullmatch(self.digest) is None or canonical_digest(self.payload) != self.digest:
            raise ValueError("revision digest must match its canonical JSON")
        _aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class DocumentEvidence:
    id: UUID
    record_id: UUID
    revision: int
    kind: EvidenceKind
    actor_id: UUID | None
    evidence: Mapping[str, DocumentValue]
    digest: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("evidence revision must be positive")
        _json_value(self.evidence)
        if _SHA256.fullmatch(self.digest) is None or canonical_digest(self.evidence) != self.digest:
            raise ValueError("evidence digest must match its canonical JSON")
        _aware(self.occurred_at, "occurred_at")


__all__ = [
    "DocumentDefinition",
    "DocumentEvidence",
    "DocumentRecord",
    "DocumentRevision",
    "DocumentScalar",
    "DocumentValue",
    "EvidenceKind",
    "canonical_digest",
]
