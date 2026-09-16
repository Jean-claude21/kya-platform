"""Neon catalog discovery never expands beyond OpenFGA-authorized identifiers."""

from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.catalog import CatalogBrowseQuery
from kya_platform.application.publication.integrity import (
    Ed25519ArtifactSigner,
    InMemoryTrustStore,
    TrustedSigningKey,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogInstallation,
    CatalogRelease,
)
from kya_platform.infrastructure.database.registry_mcp import SqlAlchemyRegistryMcpBackend
from kya_platform.mcp.registry.contracts import (
    Confirmation,
    GetArtifactInput,
    InstallationProfile,
    RequestInstallInput,
    SearchCatalogInput,
)

ALLOWED = UUID("01991c00-0000-7000-8000-000000000001")
WORKSPACE = UUID("01991c00-0000-7000-8000-000000000002")
OWNER = UUID("01991c00-0000-7000-8000-000000000003")
VERSION = UUID("01991c00-0000-7000-8000-000000000004")
RELEASE = UUID("01991c00-0000-7000-8000-000000000005")
SIGNED_AT = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)


def rows(*, status: str = "draft") -> tuple[CatalogArtifact, CatalogArtifactVersion]:
    artifact = CatalogArtifact(
        id=ALLOWED,
        registry_id="kya",
        slug="document-standard",
        artifact_type="skill",
        name="Standard documentaire KYA",
        summary="Produit les documents conformes à la charte KYA.",
        owner_workspace_id=WORKSPACE,
        business_owner_id=OWNER,
        technical_owner_id=OWNER,
        visibility="private",
        lifecycle="draft",
    )
    version = CatalogArtifactVersion(
        id=VERSION,
        artifact_id=ALLOWED,
        version="1.0.0",
        status=status,
        source_repository="https://github.com/kya-energy/document-standard",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={"compatibility": {"codex": ">=2026-09", "portable-zip": ">=1"}},
        inventory_digest="d" * 64,
        package_size=100,
        file_count=2,
        has_executable_content=False,
        risk="read",
        created_by=OWNER,
    )
    return artifact, version


class Result:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class Session:
    def __init__(self, *, scalar_values: list[UUID | None], results: list[Result]) -> None:
        self.scalar_values = scalar_values
        self.results = results
        self.statements: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, statement: object) -> UUID | None:
        self.statements.append(statement)
        return self.scalar_values.pop(0)

    async def execute(self, statement: object) -> Result:
        self.statements.append(statement)
        return self.results.pop(0)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_empty_authorization_set_never_queries_catalog() -> None:
    session = Session(scalar_values=[], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    result = await backend.search_catalog(SearchCatalogInput(query="document"), allowed_ids=())

    assert result.items == ()
    assert session.statements == []


@pytest.mark.asyncio
async def test_search_ignores_malformed_policy_ids_and_returns_only_allowed_rows() -> None:
    session = Session(scalar_values=[], results=[Result([rows()])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    result = await backend.search_catalog(
        SearchCatalogInput(query="document", types=("skill",), workspace=str(WORKSPACE)),
        allowed_ids=("not-a-uuid", str(ALLOWED)),
    )

    assert [item.artifact_id for item in result.items] == ["kya:skill:document-standard"]
    assert result.items[0].latest_version == "1.0.0"


@pytest.mark.asyncio
async def test_search_accepts_empty_query_for_a_complete_authorized_listing() -> None:
    session = Session(scalar_values=[], results=[Result([rows()])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    result = await backend.search_catalog(
        SearchCatalogInput(types=("skill",)), allowed_ids=(str(ALLOWED),)
    )

    assert [item.artifact_id for item in result.items] == ["kya:skill:document-standard"]


@pytest.mark.asyncio
async def test_invalid_workspace_filter_fails_closed_without_query() -> None:
    session = Session(scalar_values=[], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    result = await backend.search_catalog(
        SearchCatalogInput(query="document", workspace="not-a-uuid"),
        allowed_ids=(str(ALLOWED),),
    )

    assert result.items == ()
    assert session.statements == []


@pytest.mark.asyncio
async def test_resolve_rejects_non_kya_id_before_database_access() -> None:
    session = Session(scalar_values=[], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    assert await backend.resolve_artifact_id("external:skill:test") is None
    assert session.statements == []


@pytest.mark.asyncio
async def test_release_workspace_resolution_returns_published_owner() -> None:
    session = Session(scalar_values=[WORKSPACE], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    assert await backend.resolve_release_workspace(RELEASE) == str(WORKSPACE)


@pytest.mark.asyncio
async def test_release_workspace_resolution_fails_closed_when_absent() -> None:
    session = Session(scalar_values=[None], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    assert await backend.resolve_release_workspace(RELEASE) is None


@pytest.mark.asyncio
async def test_get_unknown_public_id_returns_stable_not_found() -> None:
    session = Session(scalar_values=[None], results=[])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    with pytest.raises(ToolError, match="artifact_not_found"):
        await backend.get_artifact(GetArtifactInput(artifact_id="kya:skill:unknown"))


@pytest.mark.asyncio
async def test_get_returns_versions_and_installability_without_package_content() -> None:
    artifact, draft = rows()
    _artifact, published = rows(status="published")
    published.version = "0.9.0"
    release, _trust = signed_release()
    release.artifact_version_id = published.id
    session = Session(
        scalar_values=[ALLOWED],
        results=[
            Result([(artifact, draft), (artifact, published)]),
            Result([(release, published)]),
        ],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    detail = await backend.get_artifact(GetArtifactInput(artifact_id="kya:skill:document-standard"))

    assert detail.versions == ("1.0.0", "0.9.0")
    assert detail.installable is True
    assert "installable_releases" not in detail.model_dump()


@pytest.mark.asyncio
async def test_get_does_not_claim_installability_without_a_published_release() -> None:
    artifact, published = rows(status="published")
    session = Session(
        scalar_values=[ALLOWED],
        results=[Result([(artifact, published)]), Result([])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    detail = await backend.get_artifact(GetArtifactInput(artifact_id="kya:skill:document-standard"))

    assert detail.installable is False


@pytest.mark.asyncio
async def test_release_resolution_selects_latest_published_compatible_release() -> None:
    _artifact, published = rows(status="published")
    release, _trust = signed_release()
    session = Session(
        scalar_values=[ALLOWED],
        results=[Result([(release, published)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    resolved = await backend.resolve_installable_release_id(
        artifact_id="kya:skill:document-standard",
        version="1.0.0",
        profile=InstallationProfile.CODEX,
    )

    assert resolved == RELEASE


@pytest.mark.asyncio
async def test_release_resolution_bridges_legacy_skill_to_claude_code() -> None:
    _artifact, published = rows(status="published")
    published.manifest["type"] = "skill"
    release, _trust = signed_release()
    session = Session(
        scalar_values=[ALLOWED],
        results=[Result([(release, published)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    resolved = await backend.resolve_installable_release_id(
        artifact_id="kya:skill:document-standard",
        version=None,
        profile=InstallationProfile.CLAUDE_CODE,
    )

    assert resolved == RELEASE


@pytest.mark.asyncio
async def test_release_resolution_does_not_bridge_non_skill_profiles() -> None:
    _artifact, published = rows(status="published")
    published.manifest["type"] = "application"
    release, _trust = signed_release()
    session = Session(
        scalar_values=[ALLOWED],
        results=[Result([(release, published)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    resolved = await backend.resolve_installable_release_id(
        artifact_id="kya:application:document-standard",
        version=None,
        profile=InstallationProfile.CLAUDE_CODE,
    )

    assert resolved is None


def signed_release() -> tuple[CatalogRelease, InMemoryTrustStore]:
    signer = Ed25519ArtifactSigner.from_private_key_bytes("kya-dev-2026", b"k" * 32)
    signature = signer.sign(VERSION, "b" * 64, signed_at=SIGNED_AT)
    release = CatalogRelease(
        id=RELEASE,
        artifact_version_id=VERSION,
        content_digest="b" * 64,
        signature=signature.model_dump(mode="json"),
        storage_locator="git+https://github.com/kya-energy/skills@" + "a" * 40 + "#one",
        status="published",
        published_at=SIGNED_AT,
        published_by=OWNER,
    )
    trust = InMemoryTrustStore(
        (TrustedSigningKey(key_id=signer.key_id, public_key=signer.public_key_bytes()),)
    )
    return release, trust


def install_request() -> RequestInstallInput:
    return RequestInstallInput(
        release_id=RELEASE,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        idempotency_key="install-document-0001",
        confirmation=Confirmation(confirmed=True),
    )


@pytest.mark.asyncio
async def test_install_plan_requires_configured_signing_trust() -> None:
    backend = SqlAlchemyRegistryMcpBackend(Sessions(Session(scalar_values=[], results=[])))  # type: ignore[arg-type]

    with pytest.raises(ToolError, match="installation_trust_unavailable"):
        await backend.request_install(install_request())


@pytest.mark.asyncio
async def test_install_plan_is_built_only_from_a_verified_published_release() -> None:
    artifact, version = rows(status="published")
    release, trust = signed_release()
    session = Session(scalar_values=[], results=[Result([(release, version, artifact)])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust)  # type: ignore[arg-type]

    plan = await backend.request_install(install_request())

    assert plan.release_id == RELEASE
    assert plan.content_digest == "b" * 64
    assert plan.destination == "${CODEX_PERSONAL_SKILLS_DIR}/document-standard"
    assert plan.server_writes_local_files is False


@pytest.mark.asyncio
async def test_install_plan_bridges_legacy_codex_skill_to_claude_code() -> None:
    artifact, version = rows(status="published")
    release, trust = signed_release()
    session = Session(scalar_values=[], results=[Result([(release, version, artifact)])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust)  # type: ignore[arg-type]
    request = install_request().model_copy(update={"profile": InstallationProfile.CLAUDE_CODE})

    plan = await backend.request_install(request)

    assert plan.profile is InstallationProfile.CLAUDE_CODE
    assert plan.compatibility_requirement == ">=2026-09"
    assert plan.destination == "~/.claude/skills/document-standard"


@pytest.mark.asyncio
async def test_install_plan_rejects_a_tampered_release_signature() -> None:
    artifact, version = rows(status="published")
    release, trust = signed_release()
    release.signature = {**release.signature, "signature": "tampered"}
    session = Session(scalar_values=[], results=[Result([(release, version, artifact)])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust)  # type: ignore[arg-type]

    with pytest.raises(ToolError, match="release_signature_invalid_signature"):
        await backend.request_install(install_request())


@pytest.mark.asyncio
async def test_install_plan_rejects_an_incompatible_client() -> None:
    artifact, version = rows(status="published")
    version.manifest["compatibility"]["codex"] = ">=2027"
    release, trust = signed_release()
    session = Session(scalar_values=[], results=[Result([(release, version, artifact)])])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session), trust)  # type: ignore[arg-type]

    with pytest.raises(ToolError, match="target_profile_incompatible"):
        await backend.request_install(install_request())


def installation() -> CatalogInstallation:
    return CatalogInstallation(
        id=UUID("01991c00-0000-7000-8000-000000000006"),
        artifact_id=ALLOWED,
        target="workspace:dss",
        profile="codex",
        scope="personal",
        client_version="2026-09",
        active_release_id=RELEASE,
        status="active",
        installed_by=OWNER,
        revision=1,
    )


def candidate(version_number: str, release_suffix: int):
    _artifact, version = rows(status="published")
    version.id = UUID(f"01991c00-0000-7000-8000-{release_suffix:012d}")
    version.version = version_number
    release, _trust = signed_release()
    release.id = UUID(f"01991c00-0000-7000-9000-{release_suffix:012d}")
    release.artifact_version_id = version.id
    return release, version


def test_update_resolution_selects_latest_compatible_release_and_policy() -> None:
    current = candidate("1.0.0", 10)[1]
    patch = candidate("1.0.2", 11)
    major = candidate("2.0.0", 12)

    selected = SqlAlchemyRegistryMcpBackend._latest_compatible_candidate(
        installation(), current, [patch, major]
    )

    assert selected is not None
    assert selected[1].version == "2.0.0"
    assert selected[2].value == "require-approval"


def test_update_resolution_ignores_incompatible_or_invalid_versions() -> None:
    current = candidate("1.0.0", 20)[1]
    incompatible = candidate("1.1.0", 21)
    incompatible[1].manifest["compatibility"]["codex"] = ">=2027"
    invalid = candidate("not-semver", 22)

    selected = SqlAlchemyRegistryMcpBackend._latest_compatible_candidate(
        installation(), current, [incompatible, invalid]
    )

    assert selected is None


@pytest.mark.asyncio
async def test_browse_discoverable_excludes_already_accessible_ids_and_joins_owner_name() -> None:
    artifact, _ = rows(status="published")
    result = Result([(artifact, "Équipe Data")])
    session = Session(scalar_values=[], results=[result])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    items = await backend.browse_discoverable(
        query=CatalogBrowseQuery(limit=10), excluded_ids=(str(WORKSPACE),)
    )

    assert len(items) == 1
    assert items[0].public_id == "kya:skill:document-standard"
    assert items[0].owner_workspace_name == "Équipe Data"
    assert items[0].installable is False


@pytest.mark.asyncio
async def test_browse_discoverable_returns_nothing_without_matches() -> None:
    result = Result([])
    session = Session(scalar_values=[], results=[result])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    items = await backend.browse_discoverable(
        query=CatalogBrowseQuery(query="solaire", limit=10), excluded_ids=()
    )

    assert items == ()
