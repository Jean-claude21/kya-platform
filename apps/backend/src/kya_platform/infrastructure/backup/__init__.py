"""Authenticated, encrypted and portable backups for foundation state."""

import base64
import hashlib
import json
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field

_FORMAT = "kya-foundation-backup-v1"
_AAD = b"KYA-PLATFORM-FOUNDATION-BACKUP-V1"


class BackupIntegrityError(RuntimeError):
    """The bundle cannot be authenticated or does not match its manifest."""


class BackupComponent(StrEnum):
    NEON = "neon"
    OPENFGA = "openfga"
    INFISICAL_METADATA = "infisical_metadata"


@dataclass(frozen=True, slots=True)
class BackupSource:
    component: BackupComponent
    filename: str
    content: bytes


class BackupArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: BackupComponent
    filename: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: str = Field(pattern=r"^kya-foundation-backup-v1$")
    created_at: datetime
    artifacts: tuple[BackupArtifact, ...]


def _safe_filename(filename: str) -> str:
    path = PurePath(filename)
    if path.name != filename or filename in {".", ".."}:
        raise ValueError("backup filename must be a plain basename")
    return filename


def _reject_infisical_values(source: BackupSource) -> None:
    if source.component is not BackupComponent.INFISICAL_METADATA:
        return
    try:
        document = json.loads(source.content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Infisical metadata must be valid JSON") from error

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if any(str(key).casefold() in {"secretvalue", "secret_value"} for key in value):
                raise ValueError("Infisical backup cannot contain secret values")
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(document)


def sanitize_infisical_metadata(value: object) -> object:
    """Remove secret-value fields defensively at any response depth."""

    if isinstance(value, dict):
        return {
            key: sanitize_infisical_metadata(nested)
            for key, nested in value.items()
            if str(key).casefold() not in {"secretvalue", "secret_value"}
        }
    if isinstance(value, list):
        return [sanitize_infisical_metadata(nested) for nested in value]
    return value


def _validate_key(encryption_key: bytes) -> None:
    if len(encryption_key) != 32:
        raise ValueError("backup encryption key must contain exactly 32 bytes")


def create_backup_bundle(
    path: Path,
    *,
    sources: Iterable[BackupSource],
    encryption_key: bytes,
    clock: Callable[[], datetime] | None = None,
) -> BackupManifest:
    """Seal all foundation components into one authenticated AES-256-GCM bundle."""

    _validate_key(encryption_key)
    source_items = tuple(sources)
    for source in source_items:
        _safe_filename(source.filename)
        _reject_infisical_values(source)
    components = [source.component for source in source_items]
    if len(components) != len(set(components)):
        raise ValueError("backup components must be unique")
    if set(components) != set(BackupComponent):
        raise ValueError("backup must contain every foundation component")

    created_at = (clock or (lambda: datetime.now(UTC)))()
    if created_at.tzinfo is None:
        raise ValueError("backup time must be timezone-aware")
    manifest = BackupManifest(
        format=_FORMAT,
        created_at=created_at,
        artifacts=tuple(
            BackupArtifact(
                component=source.component,
                filename=source.filename,
                sha256=hashlib.sha256(source.content).hexdigest(),
                size=len(source.content),
            )
            for source in source_items
        ),
    )
    plaintext = json.dumps(
        {
            "manifest": manifest.model_dump(mode="json"),
            "files": {
                source.filename: base64.b64encode(source.content).decode("ascii")
                for source in source_items
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, _AAD)
    envelope = {
        "format": _FORMAT,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
    return manifest


def _open_bundle(path: Path, encryption_key: bytes) -> tuple[BackupManifest, dict[str, bytes]]:
    _validate_key(encryption_key)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope.get("format") != _FORMAT:
            raise BackupIntegrityError("unsupported backup format")
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        plaintext = AESGCM(encryption_key).decrypt(nonce, ciphertext, _AAD)
        document = json.loads(plaintext)
        manifest = BackupManifest.model_validate(document["manifest"])
        files = {
            _safe_filename(filename): base64.b64decode(value, validate=True)
            for filename, value in document["files"].items()
        }
    except BackupIntegrityError:
        raise
    except (InvalidTag, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise BackupIntegrityError("backup authentication or decoding failed") from error

    expected_names = {artifact.filename for artifact in manifest.artifacts}
    if set(files) != expected_names or set(item.component for item in manifest.artifacts) != set(
        BackupComponent
    ):
        raise BackupIntegrityError("backup manifest is incomplete")
    for artifact in manifest.artifacts:
        content = files[artifact.filename]
        if len(content) != artifact.size or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise BackupIntegrityError("backup artifact digest mismatch")
    return manifest, files


def verify_backup_bundle(path: Path, *, encryption_key: bytes) -> BackupManifest:
    manifest, _files = _open_bundle(path, encryption_key)
    return manifest


def restore_backup_bundle(
    path: Path,
    *,
    target_directory: Path,
    encryption_key: bytes,
) -> tuple[Path, ...]:
    """Restore only into a new or empty directory to prevent accidental overwrites."""

    if target_directory.exists() and any(target_directory.iterdir()):
        raise FileExistsError("restore target must be empty")
    manifest, files = _open_bundle(path, encryption_key)
    target_directory.mkdir(parents=True, exist_ok=True)
    restored: list[Path] = []
    for artifact in manifest.artifacts:
        target = target_directory / artifact.filename
        target.write_bytes(files[artifact.filename])
        restored.append(target)
    return tuple(restored)


__all__ = [
    "BackupArtifact",
    "BackupComponent",
    "BackupIntegrityError",
    "BackupManifest",
    "BackupSource",
    "create_backup_bundle",
    "restore_backup_bundle",
    "sanitize_infisical_metadata",
    "verify_backup_bundle",
]
