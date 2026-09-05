"""Encrypted backup bundles detect tampering and restore into an empty target."""

import base64
import json
from pathlib import Path

import pytest

from kya_platform.infrastructure.backup import (
    BackupComponent,
    BackupIntegrityError,
    BackupSource,
    create_backup_bundle,
    restore_backup_bundle,
    sanitize_infisical_metadata,
    verify_backup_bundle,
)

KEY = bytes(range(32))


def sources() -> tuple[BackupSource, ...]:
    return (
        BackupSource(BackupComponent.NEON, "neon.dump", b"PGDMP\x00synthetic"),
        BackupSource(
            BackupComponent.OPENFGA,
            "openfga.json",
            json.dumps({"model": {"schema_version": "1.1"}, "tuples": []}).encode(),
        ),
        BackupSource(
            BackupComponent.INFISICAL_METADATA,
            "infisical-metadata.json",
            json.dumps({"secrets": [{"secretKey": "COOLIFY_API_TOKEN", "id": "ref-1"}]}).encode(),
        ),
    )


def test_round_trip_is_encrypted_verified_and_complete(tmp_path: Path) -> None:
    bundle = tmp_path / "foundation.kyabackup"
    create_backup_bundle(bundle, sources=sources(), encryption_key=KEY)

    raw = bundle.read_bytes()
    manifest = verify_backup_bundle(bundle, encryption_key=KEY)
    restored = restore_backup_bundle(
        bundle,
        target_directory=tmp_path / "restore",
        encryption_key=KEY,
    )

    assert b"COOLIFY_API_TOKEN" not in raw
    assert {item.component for item in manifest.artifacts} == set(BackupComponent)
    assert {path.name for path in restored} == {
        "neon.dump",
        "openfga.json",
        "infisical-metadata.json",
    }


def test_tampered_bundle_fails_closed(tmp_path: Path) -> None:
    bundle = tmp_path / "foundation.kyabackup"
    create_backup_bundle(bundle, sources=sources(), encryption_key=KEY)
    document = json.loads(bundle.read_text(encoding="utf-8"))
    ciphertext = bytearray(base64.b64decode(document["ciphertext"]))
    ciphertext[-1] ^= 1
    document["ciphertext"] = base64.b64encode(ciphertext).decode()
    bundle.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BackupIntegrityError, match="authentication"):
        verify_backup_bundle(bundle, encryption_key=KEY)


def test_infisical_secret_values_are_rejected_before_backup(tmp_path: Path) -> None:
    unsafe = BackupSource(
        BackupComponent.INFISICAL_METADATA,
        "infisical-metadata.json",
        json.dumps({"secrets": [{"secretKey": "TOKEN", "secretValue": "leak"}]}).encode(),
    )

    with pytest.raises(ValueError, match="secret values"):
        create_backup_bundle(tmp_path / "unsafe.kyabackup", sources=(unsafe,), encryption_key=KEY)


def test_restore_refuses_non_empty_target(tmp_path: Path) -> None:
    bundle = tmp_path / "foundation.kyabackup"
    create_backup_bundle(bundle, sources=sources(), encryption_key=KEY)
    target = tmp_path / "restore"
    target.mkdir()
    (target / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(FileExistsError, match="empty"):
        restore_backup_bundle(bundle, target_directory=target, encryption_key=KEY)


def test_infisical_export_strips_values_at_every_depth() -> None:
    source = {
        "secrets": [{"id": "one", "secretValue": "hidden"}],
        "imports": [{"secrets": [{"id": "two", "secret_value": "hidden"}]}],
    }

    sanitized = sanitize_infisical_metadata(source)
    serialized = json.dumps(sanitized)

    assert "secretValue" not in serialized
    assert "secret_value" not in serialized
    assert "hidden" not in serialized
