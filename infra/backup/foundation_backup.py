"""Create, verify and restore a KYA foundation backup bundle."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

from kya_platform.infrastructure.backup import (
    BackupComponent,
    BackupSource,
    create_backup_bundle,
    restore_backup_bundle,
    verify_backup_bundle,
)


def encryption_key() -> bytes:
    encoded = os.environ.get("KYA_BACKUP_ENCRYPTION_KEY", "")
    try:
        key = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise SystemExit("KYA_BACKUP_ENCRYPTION_KEY must be valid base64") from error
    if len(key) != 32:
        raise SystemExit("KYA_BACKUP_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subcommands = command.add_subparsers(dest="action", required=True)

    create = subcommands.add_parser("create")
    create.add_argument("--neon", type=Path, required=True)
    create.add_argument("--openfga", type=Path, required=True)
    create.add_argument("--infisical-metadata", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)

    verify = subcommands.add_parser("verify")
    verify.add_argument("bundle", type=Path)

    restore = subcommands.add_parser("restore")
    restore.add_argument("bundle", type=Path)
    restore.add_argument("--target", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    key = encryption_key()
    if arguments.action == "create":
        manifest = create_backup_bundle(
            arguments.output,
            sources=(
                BackupSource(BackupComponent.NEON, "neon.dump", arguments.neon.read_bytes()),
                BackupSource(
                    BackupComponent.OPENFGA,
                    "openfga.fga.yaml",
                    arguments.openfga.read_bytes(),
                ),
                BackupSource(
                    BackupComponent.INFISICAL_METADATA,
                    "infisical-metadata.json",
                    arguments.infisical_metadata.read_bytes(),
                ),
            ),
            encryption_key=key,
        )
        print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False))
        return 0
    if arguments.action == "verify":
        manifest = verify_backup_bundle(arguments.bundle, encryption_key=key)
        print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False))
        return 0
    restored = restore_backup_bundle(
        arguments.bundle,
        target_directory=arguments.target,
        encryption_key=key,
    )
    print(json.dumps({"restored": [str(path) for path in restored]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
