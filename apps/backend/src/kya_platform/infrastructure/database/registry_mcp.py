"""Read-only Neon backend for the Registry MCP discovery tools."""

from typing import cast
from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.publication.integrity import (
    ArtifactSignature,
    InMemoryTrustStore,
    SignatureVerification,
    verify_artifact_signature,
)
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.installation_plan import (
    ClientCompatibilityError,
    InstallationPlan,
    build_installation_plan,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogRelease,
)
from kya_platform.mcp.registry.contracts import (
    ArtifactDetail,
    ArtifactSummary,
    GetArtifactInput,
    GetOperationInput,
    ListUpdatesInput,
    ListUpdatesOutput,
    OperationAccepted,
    OperationStatus,
    PublicationAccepted,
    PublishCandidateInput,
    RequestInstallInput,
    RequestUpdateInput,
    SearchCatalogInput,
    SearchCatalogOutput,
)


def _public_id(artifact: CatalogArtifact) -> str:
    return f"{artifact.registry_id}:{artifact.artifact_type}:{artifact.slug}"


def _uuid_identifiers(values: tuple[str, ...]) -> tuple[UUID, ...]:
    identifiers: list[UUID] = []
    for value in values:
        try:
            identifiers.append(UUID(value))
        except ValueError:
            continue
    return tuple(identifiers)


class SqlAlchemyRegistryMcpBackend:
    """Return only rows whose internal IDs were preauthorized by OpenFGA."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        trust_store: InMemoryTrustStore | None = None,
    ) -> None:
        self._sessions = sessions
        self._trust_store = trust_store

    async def resolve_artifact_id(self, public_id: str) -> UUID | None:
        parts = public_id.split(":", 2)
        if len(parts) != 3 or parts[0] != "kya":
            return None
        async with self._sessions() as session:
            return cast(
                UUID | None,
                await session.scalar(
                    select(CatalogArtifact.id).where(
                        CatalogArtifact.registry_id == parts[0],
                        CatalogArtifact.artifact_type == parts[1],
                        CatalogArtifact.slug == parts[2],
                    )
                ),
            )

    async def search_catalog(
        self, request: SearchCatalogInput, *, allowed_ids: tuple[str, ...]
    ) -> SearchCatalogOutput:
        identifiers = _uuid_identifiers(allowed_ids)
        if not identifiers:
            return SearchCatalogOutput(items=())
        normalized = request.query.strip().casefold()
        filters = [
            CatalogArtifact.id.in_(identifiers),
            or_(
                func.lower(CatalogArtifact.name).contains(normalized),
                func.lower(CatalogArtifact.slug).contains(normalized),
                func.lower(func.coalesce(CatalogArtifact.summary, "")).contains(normalized),
            ),
        ]
        if request.types:
            filters.append(
                CatalogArtifact.artifact_type.in_(tuple(item.value for item in request.types))
            )
        if request.workspace is not None:
            try:
                filters.append(CatalogArtifact.owner_workspace_id == UUID(request.workspace))
            except ValueError:
                return SearchCatalogOutput(items=())
        async with self._sessions() as session:
            result = await session.execute(
                select(CatalogArtifact, CatalogArtifactVersion)
                .join(
                    CatalogArtifactVersion,
                    CatalogArtifactVersion.artifact_id == CatalogArtifact.id,
                )
                .where(*filters)
                .order_by(
                    CatalogArtifact.updated_at.desc(), CatalogArtifactVersion.created_at.desc()
                )
                .limit(100)
            )
        items: list[ArtifactSummary] = []
        seen: set[UUID] = set()
        for artifact, version in result.all():
            if artifact.id in seen:
                continue
            seen.add(artifact.id)
            items.append(
                ArtifactSummary(
                    artifact_id=_public_id(artifact),
                    artifact_type=artifact.artifact_type,
                    name=artifact.name,
                    summary=artifact.summary,
                    latest_version=version.version,
                )
            )
            if len(items) == 20:
                break
        return SearchCatalogOutput(items=tuple(items))

    async def get_artifact(self, request: GetArtifactInput) -> ArtifactDetail:
        internal_id = await self.resolve_artifact_id(request.artifact_id)
        if internal_id is None:
            raise ToolError("artifact_not_found")
        async with self._sessions() as session:
            result = await session.execute(
                select(CatalogArtifact, CatalogArtifactVersion)
                .join(
                    CatalogArtifactVersion,
                    CatalogArtifactVersion.artifact_id == CatalogArtifact.id,
                )
                .where(CatalogArtifact.id == internal_id)
                .order_by(CatalogArtifactVersion.created_at.desc())
            )
        rows = result.all()
        if request.version is not None:
            rows = [row for row in rows if row[1].version == request.version]
        if not rows:
            raise ToolError("artifact_not_found")
        artifact = rows[0][0]
        versions = tuple(dict.fromkeys(row[1].version for row in rows))
        return ArtifactDetail(
            artifact_id=_public_id(artifact),
            artifact_type=artifact.artifact_type,
            name=artifact.name,
            summary=artifact.summary,
            latest_version=rows[0][1].version,
            versions=versions,
            installable=any(row[1].status == "published" for row in rows),
        )

    async def list_updates(self, request: ListUpdatesInput) -> ListUpdatesOutput:
        raise ToolError("tool_not_implemented")

    async def request_install(self, request: RequestInstallInput) -> InstallationPlan:
        if self._trust_store is None:
            raise ToolError("installation_trust_unavailable")
        async with self._sessions() as session:
            result = await session.execute(
                select(CatalogRelease, CatalogArtifactVersion, CatalogArtifact)
                .join(
                    CatalogArtifactVersion,
                    CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                )
                .join(CatalogArtifact, CatalogArtifact.id == CatalogArtifactVersion.artifact_id)
                .where(CatalogRelease.id == request.release_id)
            )
        rows = result.all()
        if not rows:
            raise ToolError("release_not_found")
        release, version, artifact = rows[0]
        if release.status != "published" or version.status != "published":
            raise ToolError("release_not_installable")
        if release.content_digest != version.content_digest:
            raise ToolError("release_integrity_invalid")
        try:
            signature = ArtifactSignature.model_validate(release.signature)
        except ValidationError as error:
            raise ToolError("release_signature_invalid") from error
        verification = verify_artifact_signature(
            signature,
            expected_digest=release.content_digest,
            trust_store=self._trust_store,
        )
        if verification is not SignatureVerification.VALID:
            raise ToolError(f"release_signature_{verification.value}")
        compatibility = version.manifest.get("compatibility", {})
        requirement = compatibility.get(request.profile.value)
        if not isinstance(requirement, str) or not requirement:
            raise ToolError("target_profile_incompatible")
        try:
            return build_installation_plan(
                release_id=release.id,
                artifact_id=artifact.id,
                artifact_type=ArtifactType(artifact.artifact_type),
                artifact_slug=artifact.slug,
                version=version.version,
                profile=request.profile,
                scope=request.scope,
                target=request.target,
                package_locator=release.storage_locator,
                content_digest=release.content_digest,
                compatibility_requirement=requirement,
                client_version=request.client_version,
                file_count=version.file_count,
                package_size=version.package_size,
            )
        except ClientCompatibilityError as error:
            raise ToolError("target_profile_incompatible") from error
        except ValueError as error:
            raise ToolError("installation_plan_invalid") from error

    async def request_update(self, request: RequestUpdateInput) -> OperationAccepted:
        raise ToolError("tool_not_implemented")

    async def get_operation(self, request: GetOperationInput) -> OperationStatus:
        raise ToolError("tool_not_implemented")

    async def publish_candidate(self, request: PublishCandidateInput) -> PublicationAccepted:
        raise ToolError("tool_not_implemented")


__all__ = ["SqlAlchemyRegistryMcpBackend"]
