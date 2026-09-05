"""Run a non-production round-trip drill for the encrypted backup format."""

import json
import tempfile
from pathlib import Path

from kya_platform.infrastructure.backup import (
    BackupComponent,
    BackupSource,
    create_backup_bundle,
    restore_backup_bundle,
    verify_backup_bundle,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="kya-backup-drill-") as directory:
        root = Path(directory)
        key = bytes(range(32))
        bundle = root / "foundation.kyabackup"
        sources = (
            BackupSource(BackupComponent.NEON, "neon.dump", b"PGDMP\x00drill"),
            BackupSource(
                BackupComponent.OPENFGA,
                "openfga.fga.yaml",
                b"name: KYA drill\nmodel: |\n  model\n    schema 1.1\n",
            ),
            BackupSource(
                BackupComponent.INFISICAL_METADATA,
                "infisical-metadata.json",
                b'{"secrets":[{"id":"drill","secretKey":"DRILL_KEY"}]}',
            ),
        )
        create_backup_bundle(bundle, sources=sources, encryption_key=key)
        verified = verify_backup_bundle(bundle, encryption_key=key)
        restored = restore_backup_bundle(
            bundle,
            target_directory=root / "restored",
            encryption_key=key,
        )
        if len(verified.artifacts) != 3 or len(restored) != 3:
            raise RuntimeError("backup drill is incomplete")
        print(json.dumps({"verified": True, "restored_components": 3}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
