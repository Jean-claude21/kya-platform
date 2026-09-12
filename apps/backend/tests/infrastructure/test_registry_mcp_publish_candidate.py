"""Registry MCP publish_candidate delegates to the shared publication service."""

from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.domain.catalog import PublicationRequest
from kya_platform.infrastructure.database.models import CatalogArtifact, CatalogArtifactVersion
from kya_platform.infrastructure.database.registry_mcp import SqlAlchemyRegistryMcpBackend
from kya_platform.mcp.registry.contracts import Confirmation, PublishCandidateInput

ARTIFACT = UUID("01991c00-0000-7000-8000-000000000101")
ACTOR = UUID("01991c00-0000-7000-8000-000000000102")
REQUEST_ID = UUID("01991c00-0000-7000-8000-000000000103")
NOW = datetime(2026, 9, 12, tzinfo=UTC)


def artifact_row() -> CatalogArtifact:
    return CatalogArtifact(
        id=ARTIFACT,
        registry_id="kya",
        slug="document-standard",
        artifact_type="skill",
        name="Standard documentaire KYA",
        owner_workspace_id=ARTIFACT,
        business_owner_id=ARTIFACT,
        technical_owner_id=ARTIFACT,
        visibility="private",
        lifecycle="approved",
    )


def version_row() -> CatalogArtifactVersion:
    return CatalogArtifactVersion(
        id=UUID("01991c00-0000-7000-8000-000000000104"),
        artifact_id=ARTIFACT,
        version="1.0.0",
        status="approved",
        source_repository="https://github.com/kya-energy/document-standard",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={},
        inventory_digest="d" * 64,
        package_size=10,
        file_count=1,
        has_executable_content=False,
        risk="read",
        created_by=ACTOR,
    )


class Session:
    def __init__(self, *, scalar_values: list[object]) -> None:
        self.scalar_values = scalar_values

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, statement: object) -> object:
        del statement
        return self.scalar_values.pop(0)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


class FakePublicationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.raise_value_error = False

    async def submit(self, **kwargs: object) -> PublicationRequest:
        self.calls.append(kwargs)
        if self.raise_value_error:
            raise ValueError("candidate does not match a persisted artifact version")
        candidate = kwargs["candidate"]
        requested_by = kwargs["actor_id"]
        assert isinstance(requested_by, UUID)
        from kya_platform.domain.catalog import ArtifactVersion

        assert isinstance(candidate, ArtifactVersion)
        return PublicationRequest.open(
            id=REQUEST_ID,
            candidate=candidate,
            requested_by=requested_by,
            requested_at=NOW,
            separation_of_duties=True,
            evidence_ids=kwargs.get("evidence_ids", ()),  # type: ignore[arg-type]
        )


def request() -> PublishCandidateInput:
    return PublishCandidateInput(
        artifact_id="kya:skill:document-standard",
        version="1.0.0",
        evidence=(str(UUID(int=1)),),
        actor_id=ACTOR,
        idempotency_key="a" * 16,
        confirmation=Confirmation(confirmed=True),
    )


@pytest.mark.asyncio
async def test_publish_candidate_fails_closed_without_a_configured_service() -> None:
    session = Session(scalar_values=[ARTIFACT])
    backend = SqlAlchemyRegistryMcpBackend(Sessions(session))  # type: ignore[arg-type]

    with pytest.raises(ToolError, match="publication_service_unavailable"):
        await backend.publish_candidate(request())


@pytest.mark.asyncio
async def test_publish_candidate_rejects_an_unknown_artifact() -> None:
    session = Session(scalar_values=[None])
    service = FakePublicationService()
    backend = SqlAlchemyRegistryMcpBackend(
        Sessions(session),
        publication_service=service,  # type: ignore[arg-type]
    )

    with pytest.raises(ToolError, match="artifact_not_found"):
        await backend.publish_candidate(request())
    assert service.calls == []


@pytest.mark.asyncio
async def test_publish_candidate_rejects_an_unknown_version() -> None:
    session = Session(scalar_values=[ARTIFACT, None])
    service = FakePublicationService()
    backend = SqlAlchemyRegistryMcpBackend(
        Sessions(session),
        publication_service=service,  # type: ignore[arg-type]
    )

    with pytest.raises(ToolError, match="artifact_version_not_found"):
        await backend.publish_candidate(request())
    assert service.calls == []


@pytest.mark.asyncio
async def test_publish_candidate_rejects_malformed_evidence_identifiers() -> None:
    session = Session(scalar_values=[ARTIFACT, version_row()])
    service = FakePublicationService()
    backend = SqlAlchemyRegistryMcpBackend(
        Sessions(session),
        publication_service=service,  # type: ignore[arg-type]
    )
    malformed = PublishCandidateInput(
        artifact_id="kya:skill:document-standard",
        version="1.0.0",
        evidence=("not-a-uuid",),
        actor_id=ACTOR,
        idempotency_key="a" * 16,
        confirmation=Confirmation(confirmed=True),
    )

    with pytest.raises(ToolError, match="evidence_identifier_invalid"):
        await backend.publish_candidate(malformed)
    assert service.calls == []


@pytest.mark.asyncio
async def test_publish_candidate_submits_the_persisted_candidate_version() -> None:
    session = Session(scalar_values=[ARTIFACT, version_row()])
    service = FakePublicationService()
    backend = SqlAlchemyRegistryMcpBackend(
        Sessions(session),
        publication_service=service,  # type: ignore[arg-type]
    )

    accepted = await backend.publish_candidate(request())

    assert accepted.request_id == REQUEST_ID
    assert accepted.status == "submitted"
    assert len(service.calls) == 1
    submitted_candidate = service.calls[0]["candidate"]
    assert submitted_candidate.content_digest == "b" * 64  # type: ignore[union-attr]
    assert service.calls[0]["actor_id"] == ACTOR


@pytest.mark.asyncio
async def test_publish_candidate_translates_a_domain_rejection() -> None:
    session = Session(scalar_values=[ARTIFACT, version_row()])
    service = FakePublicationService()
    service.raise_value_error = True
    backend = SqlAlchemyRegistryMcpBackend(
        Sessions(session),
        publication_service=service,  # type: ignore[arg-type]
    )

    with pytest.raises(ToolError, match="publication_candidate_invalid"):
        await backend.publish_candidate(request())
