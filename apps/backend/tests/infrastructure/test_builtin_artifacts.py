"""The one-time builtin release repair is immutable, verified and idempotent."""

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.infrastructure.database import builtin_artifacts
from kya_platform.infrastructure.database.models import (
    CatalogArtifactVersion,
    CatalogPackageFile,
    CatalogRelease,
    OutboxEvent,
)


class Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class Session:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.added: list[object] = []

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, _statement: object) -> object:
        return self.values.pop(0)

    def begin(self) -> Transaction:
        return Transaction()

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, sessions: list[Session]) -> None:
        self.sessions = sessions

    def __call__(self) -> Session:
        return self.sessions.pop(0)


def artifact() -> Any:
    return SimpleNamespace(
        id=uuid4(),
        technical_owner_id=uuid4(),
        lifecycle="published",
    )


@pytest.mark.asyncio
async def test_recovery_is_a_noop_when_builtin_artifact_is_absent() -> None:
    changed = await builtin_artifacts.ensure_design_system_recovery_release(
        Sessions([Session([None])]),  # type: ignore[arg-type]
        Ed25519ArtifactSigner.generate("test-key"),
    )

    assert changed is False


@pytest.mark.asyncio
async def test_recovery_is_a_noop_when_corrective_version_exists() -> None:
    changed = await builtin_artifacts.ensure_design_system_recovery_release(
        Sessions([Session([artifact(), uuid4()])]),  # type: ignore[arg-type]
        Ed25519ArtifactSigner.generate("test-key"),
    )

    assert changed is False


@pytest.mark.asyncio
async def test_recovery_adds_a_verified_signed_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = builtin_artifacts.design_system_archive_bytes()
    monkeypatch.setattr(builtin_artifacts, "design_system_archive_bytes", lambda: archive)
    owned = artifact()
    write = Session([owned, None])

    changed = await builtin_artifacts.ensure_design_system_recovery_release(
        Sessions([Session([owned, None]), write]),  # type: ignore[arg-type]
        Ed25519ArtifactSigner.generate("test-key"),
    )

    assert changed is True
    version = next(item for item in write.added if isinstance(item, CatalogArtifactVersion))
    release = next(item for item in write.added if isinstance(item, CatalogRelease))
    files = [item for item in write.added if isinstance(item, CatalogPackageFile)]
    event = next(item for item in write.added if isinstance(item, OutboxEvent))
    assert version.version == "0.1.2"
    assert version.status == "published"
    assert release.artifact_version_id == version.id
    assert release.content_digest == version.content_digest
    assert release.storage_locator == builtin_artifacts._ARCHIVE_URL
    assert release.signature["content_digest"] == version.content_digest
    assert len(files) == 7
    assert event.topic == "artifact.release.recovered"


@pytest.mark.asyncio
async def test_recovery_rejects_changed_release_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        builtin_artifacts,
        "design_system_archive_bytes",
        lambda: (_ for _ in ()).throw(RuntimeError("archive digest mismatch")),
    )

    with pytest.raises(RuntimeError, match="archive digest mismatch"):
        await builtin_artifacts.ensure_design_system_recovery_release(
            Sessions([Session([artifact(), None])]),  # type: ignore[arg-type]
            Ed25519ArtifactSigner.generate("test-key"),
        )
