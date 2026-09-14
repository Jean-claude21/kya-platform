"""Transactional Registry distribution commands remain idempotent and fail closed."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.publication.integrity import (
    Ed25519ArtifactSigner,
    InMemoryTrustStore,
    TrustedSigningKey,
)
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.installation_plan import (
    InstallationProfile,
    InstallationScope,
    build_installation_plan,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogDistributionOperation,
    CatalogInstallation,
    CatalogRelease,
)
from kya_platform.infrastructure.database.registry_mcp import SqlAlchemyRegistryMcpBackend
from kya_platform.mcp.registry import (
    Confirmation,
    ConfirmInstallationInput,
    ConfirmUpdateInput,
    GetOperationInput,
    InstallationAction,
    ListUpdatesInput,
    ManageInstallationInput,
    RequestUpdateInput,
)

ARTIFACT_ID = UUID("01991d00-0000-7000-8000-000000000001")
VERSION_ID = UUID("01991d00-0000-7000-8000-000000000002")
RELEASE_ID = UUID("01991d00-0000-7000-8000-000000000003")
INSTALLATION_ID = UUID("01991d00-0000-7000-8000-000000000004")
ACTOR_ID = UUID("01991d00-0000-7000-8000-000000000005")
WORKSPACE_ID = UUID("01991d00-0000-7000-8000-000000000006")


class Rows:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def all(self) -> list[Any]:
        return self.rows

    def tuples(self) -> Rows:
        return self


class LifecycleSession:
    def __init__(
        self,
        *,
        scalars: list[Any] | None = None,
        gets: list[Any] | None = None,
        executes: list[Rows] | None = None,
        scalar_rows: list[Rows] | None = None,
    ) -> None:
        self.scalar_values = list(scalars or [])
        self.get_values = list(gets or [])
        self.execute_values = list(executes or [])
        self.scalar_rows = list(scalar_rows or [])
        self.added: list[Any] = []

    async def __aenter__(self) -> LifecycleSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    @asynccontextmanager
    async def begin(self):  # type: ignore[no-untyped-def]
        yield self

    async def scalar(self, _statement: object) -> Any:
        return self.scalar_values.pop(0)

    async def get(self, _model: object, _identifier: UUID) -> Any:
        return self.get_values.pop(0)

    async def execute(self, _statement: object) -> Rows:
        return self.execute_values.pop(0)

    async def scalars(self, _statement: object) -> Rows:
        return self.scalar_rows.pop(0)

    def add_all(self, values: list[Any]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, session: LifecycleSession) -> None:
        self.session = session

    def __call__(self) -> LifecycleSession:
        return self.session


def release_rows() -> tuple[CatalogRelease, CatalogArtifactVersion, CatalogArtifact]:
    artifact = CatalogArtifact(
        id=ARTIFACT_ID,
        registry_id="kya",
        slug="document-standard",
        artifact_type="skill",
        name="Standard documentaire",
        owner_workspace_id=WORKSPACE_ID,
        business_owner_id=ACTOR_ID,
        technical_owner_id=ACTOR_ID,
        visibility="private",
        lifecycle="published",
    )
    version = CatalogArtifactVersion(
        id=VERSION_ID,
        artifact_id=ARTIFACT_ID,
        version="1.0.0",
        status="published",
        source_repository="https://github.com/kya/skills",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={"compatibility": {"codex": ">=2026-09"}},
        inventory_digest="d" * 64,
        package_size=100,
        file_count=2,
        has_executable_content=False,
        risk="read",
        created_by=ACTOR_ID,
    )
    signer = Ed25519ArtifactSigner.from_private_key_bytes("test", b"k" * 32)
    release = CatalogRelease(
        id=RELEASE_ID,
        artifact_version_id=VERSION_ID,
        content_digest="b" * 64,
        signature=signer.sign(
            VERSION_ID, "b" * 64, signed_at=datetime(2026, 9, 7, tzinfo=UTC)
        ).model_dump(mode="json"),
        storage_locator="https://packages.kya.energy/document-standard.zip",
        status="published",
        published_at=datetime(2026, 9, 7, tzinfo=UTC),
        published_by=ACTOR_ID,
    )
    return release, version, artifact


def trust() -> InMemoryTrustStore:
    signer = Ed25519ArtifactSigner.from_private_key_bytes("test", b"k" * 32)
    return InMemoryTrustStore(
        (TrustedSigningKey(key_id="test", public_key=signer.public_key_bytes()),)
    )


@pytest.mark.asyncio
async def test_distribution_resources_resolve_to_their_workspace() -> None:
    installation_backend = SqlAlchemyRegistryMcpBackend(  # type: ignore[arg-type]
        Sessions(LifecycleSession(scalars=["workspace:dss"]))
    )
    operation_backend = SqlAlchemyRegistryMcpBackend(  # type: ignore[arg-type]
        Sessions(LifecycleSession(scalars=["workspace:dss"]))
    )

    assert await installation_backend.resolve_installation_workspace(INSTALLATION_ID) == "dss"
    assert await operation_backend.resolve_operation_workspace(RELEASE_ID) == "dss"

    invalid_installation_backend = SqlAlchemyRegistryMcpBackend(  # type: ignore[arg-type]
        Sessions(LifecycleSession(scalars=["personal:alice"]))
    )
    invalid_operation_backend = SqlAlchemyRegistryMcpBackend(  # type: ignore[arg-type]
        Sessions(LifecycleSession(scalars=[None]))
    )
    assert (
        await invalid_installation_backend.resolve_installation_workspace(INSTALLATION_ID) is None
    )
    assert await invalid_operation_backend.resolve_operation_workspace(RELEASE_ID) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    (InstallationProfile.CODEX, InstallationProfile.CLAUDE_CODE),
)
async def test_confirm_installation_records_receipt_history_operation_and_outbox(
    profile: InstallationProfile,
) -> None:
    release, version, artifact = release_rows()
    plan = build_installation_plan(
        release_id=RELEASE_ID,
        artifact_id=ARTIFACT_ID,
        artifact_type=ArtifactType.SKILL,
        artifact_slug=artifact.slug,
        version=version.version,
        profile=profile,
        scope=InstallationScope.PERSONAL,
        target="workspace:dss",
        package_locator=release.storage_locator,
        content_digest=release.content_digest,
        compatibility_requirement=">=2026-09",
        client_version="2026-09",
        file_count=2,
        package_size=100,
    )
    session = LifecycleSession(
        scalars=[None, None], executes=[Rows([(release, version, artifact)])]
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust())  # type: ignore[arg-type]

    recorded = await backend.confirm_installation(
        ConfirmInstallationInput(
            plan_id=plan.plan_id,
            release_id=RELEASE_ID,
            target="workspace:dss",
            profile=profile,
            scope="personal",
            client_version="2026-09",
            installed_digest="b" * 64,
            actor_id=ACTOR_ID,
            idempotency_key="confirm-installation-0001",
            confirmation=Confirmation(confirmed=True),
        )
    )

    assert recorded.status == "active"
    assert len(session.added) == 4
    assert any(item.__class__.__name__ == "CatalogInstallationHistory" for item in session.added)


@pytest.mark.asyncio
async def test_update_request_is_idempotent_and_detects_key_conflict() -> None:
    existing = CatalogDistributionOperation(
        id=UUID("01991d00-0000-7000-8000-000000000010"),
        installation_id=INSTALLATION_ID,
        release_id=RELEASE_ID,
        kind="update",
        status="accepted",
        actor_id=ACTOR_ID,
        idempotency_key="update-installation-0001",
        request_hash="wrong",
        result={},
    )
    session = LifecycleSession(scalars=[existing])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]
    request = RequestUpdateInput(
        installation_id=INSTALLATION_ID,
        release_id=RELEASE_ID,
        actor_id=ACTOR_ID,
        idempotency_key="update-installation-0001",
        confirmation=Confirmation(confirmed=True),
    )

    with pytest.raises(ToolError, match="idempotency_key_conflict"):
        await backend.request_update(request)


@pytest.mark.asyncio
async def test_update_request_persists_operation_and_outbox_atomically() -> None:
    release, version, _artifact = release_rows()
    installation = CatalogInstallation(
        id=INSTALLATION_ID,
        artifact_id=ARTIFACT_ID,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=UUID("01991d00-0000-7000-9000-000000000007"),
        status="active",
        installed_by=ACTOR_ID,
        revision=1,
    )
    session = LifecycleSession(
        scalars=[None],
        gets=[installation],
        executes=[Rows([(release, version)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust())  # type: ignore[arg-type]

    accepted = await backend.request_update(
        RequestUpdateInput(
            installation_id=INSTALLATION_ID,
            release_id=RELEASE_ID,
            actor_id=ACTOR_ID,
            idempotency_key="update-installation-0002",
            confirmation=Confirmation(confirmed=True),
        )
    )

    assert accepted.status == "accepted"
    assert len(session.added) == 2
    assert session.added[0].kind == "update"


@pytest.mark.asyncio
async def test_manage_installation_revokes_with_optimistic_revision_and_audit() -> None:
    installation = CatalogInstallation(
        id=INSTALLATION_ID,
        artifact_id=ARTIFACT_ID,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=RELEASE_ID,
        status="active",
        installed_by=ACTOR_ID,
        revision=1,
    )
    session = LifecycleSession(scalars=[None, installation])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    operation = await backend.manage_installation(
        ManageInstallationInput(
            installation_id=INSTALLATION_ID,
            action=InstallationAction.REVOKE,
            expected_revision=1,
            actor_id=ACTOR_ID,
            reason="Capability compromised",
            idempotency_key="revoke-installation-0001",
            confirmation=Confirmation(confirmed=True),
        )
    )

    assert operation.status == "succeeded"
    assert installation.status == "revoked"
    assert installation.revision == 2
    assert len(session.added) == 3


@pytest.mark.asyncio
async def test_manage_installation_rolls_back_only_to_published_release() -> None:
    previous_release, _version, _artifact = release_rows()
    previous_release.id = UUID("01991d00-0000-7000-8000-000000000030")
    installation = CatalogInstallation(
        id=INSTALLATION_ID,
        artifact_id=ARTIFACT_ID,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=RELEASE_ID,
        rollback_release_id=previous_release.id,
        status="active",
        installed_by=ACTOR_ID,
        revision=2,
    )
    session = LifecycleSession(scalars=[None, installation], gets=[previous_release])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    operation = await backend.manage_installation(
        ManageInstallationInput(
            installation_id=INSTALLATION_ID,
            action=InstallationAction.ROLLBACK,
            expected_revision=2,
            actor_id=ACTOR_ID,
            reason="Regression detected",
            idempotency_key="rollback-installation-0001",
            confirmation=Confirmation(confirmed=True),
        )
    )

    assert operation.status == "rolled-back"
    assert installation.active_release_id == previous_release.id
    assert installation.rollback_release_id == RELEASE_ID


@pytest.mark.asyncio
async def test_get_operation_returns_persisted_terminal_evidence() -> None:
    operation = CatalogDistributionOperation(
        id=UUID("01991d00-0000-7000-8000-000000000020"),
        installation_id=INSTALLATION_ID,
        release_id=RELEASE_ID,
        kind="revoke",
        status="succeeded",
        actor_id=ACTOR_ID,
        idempotency_key="operation-status-0001",
        request_hash="e" * 64,
        result={},
    )
    backend = SqlAlchemyRegistryMcpBackend(  # type: ignore[arg-type]
        Sessions(LifecycleSession(gets=[operation]))
    )

    result = await backend.get_operation(GetOperationInput(operation_id=operation.id))

    assert result.status == "succeeded"


@pytest.mark.asyncio
async def test_confirm_update_moves_release_and_preserves_rollback_atomically() -> None:
    release, version, _artifact = release_rows()
    operation = CatalogDistributionOperation(
        id=UUID("01991d00-0000-7000-8000-000000000040"),
        installation_id=INSTALLATION_ID,
        release_id=RELEASE_ID,
        kind="update",
        status="accepted",
        actor_id=ACTOR_ID,
        idempotency_key="update-confirm-0001",
        request_hash="f" * 64,
        result={},
    )
    previous_release_id = UUID("01991d00-0000-7000-9000-000000000041")
    installation = CatalogInstallation(
        id=INSTALLATION_ID,
        artifact_id=ARTIFACT_ID,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=previous_release_id,
        status="active",
        installed_by=ACTOR_ID,
        revision=1,
    )
    session = LifecycleSession(
        scalars=[operation, installation],
        executes=[Rows([(release, version)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust())  # type: ignore[arg-type]

    result = await backend.confirm_update(
        ConfirmUpdateInput(
            operation_id=operation.id,
            installed_digest="b" * 64,
            expected_revision=1,
            actor_id=ACTOR_ID,
            confirmation=Confirmation(confirmed=True),
        )
    )

    assert result.status == "succeeded"
    assert installation.active_release_id == RELEASE_ID
    assert installation.rollback_release_id == previous_release_id
    assert installation.revision == 2
    assert operation.status == "succeeded"
    assert len(session.added) == 2


@pytest.mark.asyncio
async def test_list_updates_returns_only_the_latest_compatible_candidate() -> None:
    current_release, current_version, _artifact = release_rows()
    candidate_release, candidate_version, _other = release_rows()
    candidate_release.id = UUID("01991d00-0000-7000-9000-000000000050")
    candidate_version.id = UUID("01991d00-0000-7000-9000-000000000051")
    candidate_version.version = "1.1.0"
    candidate_release.artifact_version_id = candidate_version.id
    installation = CatalogInstallation(
        id=INSTALLATION_ID,
        artifact_id=ARTIFACT_ID,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=RELEASE_ID,
        status="active",
        installed_by=ACTOR_ID,
        revision=1,
    )
    session = LifecycleSession(
        scalar_rows=[Rows([installation])],
        executes=[
            Rows([(current_release, current_version)]),
            Rows([(current_release, current_version), (candidate_release, candidate_version)]),
        ],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    result = await backend.list_updates(ListUpdatesInput(installation_id=INSTALLATION_ID))

    assert len(result.items) == 1
    assert result.items[0].candidate_version == "1.1.0"
    assert result.items[0].decision == "require-approval"
