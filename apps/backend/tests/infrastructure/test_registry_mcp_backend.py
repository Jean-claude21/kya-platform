"""Neon catalog discovery never expands beyond OpenFGA-authorized identifiers."""

from typing import Self
from uuid import UUID

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.infrastructure.database.models import CatalogArtifact, CatalogArtifactVersion
from kya_platform.infrastructure.database.registry_mcp import SqlAlchemyRegistryMcpBackend
from kya_platform.mcp.registry.contracts import GetArtifactInput, SearchCatalogInput

ALLOWED = UUID("01991c00-0000-7000-8000-000000000001")
WORKSPACE = UUID("01991c00-0000-7000-8000-000000000002")
OWNER = UUID("01991c00-0000-7000-8000-000000000003")
VERSION = UUID("01991c00-0000-7000-8000-000000000004")


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
        manifest={},
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
    session = Session(
        scalar_values=[ALLOWED],
        results=[Result([(artifact, draft), (artifact, published)])],
    )
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    detail = await backend.get_artifact(GetArtifactInput(artifact_id="kya:skill:document-standard"))

    assert detail.versions == ("1.0.0", "0.9.0")
    assert detail.installable is True
