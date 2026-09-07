"""Neon backend for governed Registry discovery and distribution operations."""

import hashlib
import json
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid7

from mcp.server.mcpserver.exceptions import ToolError
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
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
from kya_platform.domain.distribution import (
    ChangeKind,
    UpdateDecision,
    UpdatePolicy,
    assess_update,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogDistributionOperation,
    CatalogInstallation,
    CatalogInstallationHistory,
    CatalogRelease,
    OutboxEvent,
)
from kya_platform.mcp.registry.contracts import (
    ArtifactDetail,
    ArtifactSummary,
    ConfirmInstallationInput,
    ConfirmUpdateInput,
    GetArtifactInput,
    GetOperationInput,
    InstallationRecorded,
    ListUpdatesInput,
    ListUpdatesOutput,
    ManageInstallationInput,
    OperationAccepted,
    OperationStatus,
    PublicationAccepted,
    PublishCandidateInput,
    RequestInstallInput,
    RequestUpdateInput,
    SearchCatalogInput,
    SearchCatalogOutput,
    UpdateSummary,
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

    async def resolve_installation_workspace(self, installation_id: UUID) -> str | None:
        async with self._sessions() as session:
            target = await session.scalar(
                select(CatalogInstallation.target).where(CatalogInstallation.id == installation_id)
            )
        if not isinstance(target, str) or not target.startswith("workspace:"):
            return None
        workspace = target.removeprefix("workspace:")
        return workspace or None

    async def resolve_operation_workspace(self, operation_id: UUID) -> str | None:
        async with self._sessions() as session:
            target = await session.scalar(
                select(CatalogInstallation.target)
                .join(
                    CatalogDistributionOperation,
                    CatalogDistributionOperation.installation_id == CatalogInstallation.id,
                )
                .where(CatalogDistributionOperation.id == operation_id)
            )
        if not isinstance(target, str) or not target.startswith("workspace:"):
            return None
        workspace = target.removeprefix("workspace:")
        return workspace or None

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
        async with self._sessions() as session:
            statement = select(CatalogInstallation)
            statement = statement.where(
                CatalogInstallation.id == request.installation_id,
                CatalogInstallation.status == "active",
            )
            installations = (await session.scalars(statement)).all()
            summaries: list[UpdateSummary] = []
            for installation in installations:
                current = (
                    (
                        await session.execute(
                            select(CatalogRelease, CatalogArtifactVersion)
                            .join(
                                CatalogArtifactVersion,
                                CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                            )
                            .where(CatalogRelease.id == installation.active_release_id)
                        )
                    )
                    .tuples()
                    .first()
                )
                if current is None:
                    continue
                _current_release, current_version = current
                candidates = (
                    (
                        await session.execute(
                            select(CatalogRelease, CatalogArtifactVersion)
                            .join(
                                CatalogArtifactVersion,
                                CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                            )
                            .where(
                                CatalogArtifactVersion.artifact_id == installation.artifact_id,
                                CatalogRelease.status == "published",
                            )
                        )
                    )
                    .tuples()
                    .all()
                )
                candidate = self._latest_compatible_candidate(
                    installation,
                    current_version,
                    list(candidates),
                )
                if candidate is None:
                    continue
                _release, version, decision = candidate
                summaries.append(
                    UpdateSummary(
                        installation_id=installation.id,
                        current_version=current_version.version,
                        candidate_version=version.version,
                        decision=decision.value,
                    )
                )
        return ListUpdatesOutput(items=tuple(summaries))

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
        self._verify_release_integrity(release, version.content_digest)
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
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "installation_id": str(request.installation_id),
                    "release_id": str(request.release_id),
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with self._sessions() as session, session.begin():
            existing = await session.scalar(
                select(CatalogDistributionOperation).where(
                    CatalogDistributionOperation.actor_id == request.actor_id,
                    CatalogDistributionOperation.idempotency_key == request.idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ToolError("idempotency_key_conflict")
                return OperationAccepted(operation_id=existing.id)
            installation = await session.get(CatalogInstallation, request.installation_id)
            if installation is None:
                raise ToolError("installation_not_found")
            if installation.status != "active":
                raise ToolError("installation_not_active")
            if installation.active_release_id == request.release_id:
                raise ToolError("already_current_release")
            release_row = (
                await session.execute(
                    select(CatalogRelease, CatalogArtifactVersion)
                    .join(
                        CatalogArtifactVersion,
                        CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                    )
                    .where(CatalogRelease.id == request.release_id)
                )
            ).first()
            if release_row is None:
                raise ToolError("release_not_found")
            release, version = release_row
            if release.status != "published" or version.artifact_id != installation.artifact_id:
                raise ToolError("release_not_installable")
            operation = CatalogDistributionOperation(
                id=uuid7(),
                installation_id=installation.id,
                release_id=release.id,
                kind="update",
                status="accepted",
                actor_id=request.actor_id,
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                result={},
            )
            session.add_all(
                [
                    operation,
                    OutboxEvent(
                        topic="artifact.update.requested",
                        aggregate_type="installation",
                        aggregate_id=str(installation.id),
                        correlation_id=operation.id,
                        payload={
                            "installation_id": str(installation.id),
                            "release_id": str(release.id),
                            "operation_id": str(operation.id),
                        },
                    ),
                ]
            )
        return OperationAccepted(operation_id=operation.id)

    async def confirm_installation(self, request: ConfirmInstallationInput) -> InstallationRecorded:
        request_payload = {
            "plan_id": str(request.plan_id),
            "release_id": str(request.release_id),
            "target": request.target,
            "profile": request.profile.value,
            "scope": request.scope.value,
            "client_version": request.client_version,
            "installed_digest": request.installed_digest,
        }
        request_hash = hashlib.sha256(
            json.dumps(request_payload, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        async with self._sessions() as session, session.begin():
            existing_operation = await session.scalar(
                select(CatalogDistributionOperation).where(
                    CatalogDistributionOperation.actor_id == request.actor_id,
                    CatalogDistributionOperation.idempotency_key == request.idempotency_key,
                )
            )
            if existing_operation is not None:
                if existing_operation.request_hash != request_hash:
                    raise ToolError("idempotency_key_conflict")
                installation_id = existing_operation.installation_id
                if installation_id is None:
                    raise ToolError("installation_receipt_invalid")
                return InstallationRecorded(
                    installation_id=installation_id,
                    operation_id=existing_operation.id,
                )
            release_row = (
                await session.execute(
                    select(CatalogRelease, CatalogArtifactVersion, CatalogArtifact)
                    .join(
                        CatalogArtifactVersion,
                        CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                    )
                    .join(CatalogArtifact, CatalogArtifact.id == CatalogArtifactVersion.artifact_id)
                    .where(CatalogRelease.id == request.release_id)
                )
            ).first()
            if release_row is None:
                raise ToolError("release_not_found")
            release, version, artifact = release_row
            if release.status != "published" or version.status != "published":
                raise ToolError("release_not_installable")
            self._verify_release_integrity(release, version.content_digest)
            if request.installed_digest != release.content_digest:
                raise ToolError("installed_digest_mismatch")
            requirement = version.manifest.get("compatibility", {}).get(request.profile.value)
            if not isinstance(requirement, str):
                raise ToolError("target_profile_incompatible")
            try:
                expected_plan = build_installation_plan(
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
            except (ClientCompatibilityError, ValueError) as error:
                raise ToolError("installation_receipt_invalid") from error
            if expected_plan.plan_id != request.plan_id:
                raise ToolError("installation_plan_mismatch")
            duplicate = await session.scalar(
                select(CatalogInstallation).where(
                    CatalogInstallation.artifact_id == artifact.id,
                    CatalogInstallation.target == request.target,
                    CatalogInstallation.profile == request.profile.value,
                    CatalogInstallation.scope == request.scope.value,
                )
            )
            if duplicate is not None:
                raise ToolError("installation_already_recorded")
            installation_id = uuid7()
            operation_id = uuid7()
            installation = CatalogInstallation(
                id=installation_id,
                artifact_id=artifact.id,
                target=request.target,
                profile=request.profile.value,
                scope=request.scope.value,
                client_version=request.client_version,
                active_release_id=release.id,
                rollback_release_id=None,
                status="active",
                installed_by=request.actor_id,
                revision=1,
            )
            session.add_all(
                [
                    installation,
                    CatalogInstallationHistory(
                        installation_id=installation_id,
                        sequence=1,
                        action="install",
                        from_release_id=None,
                        to_release_id=release.id,
                        status="active",
                        actor_id=request.actor_id,
                    ),
                    CatalogDistributionOperation(
                        id=operation_id,
                        installation_id=installation_id,
                        release_id=release.id,
                        kind="install",
                        status="succeeded",
                        actor_id=request.actor_id,
                        idempotency_key=request.idempotency_key,
                        request_hash=request_hash,
                        result={"plan_id": str(request.plan_id)},
                    ),
                    OutboxEvent(
                        topic="artifact.installed",
                        aggregate_type="installation",
                        aggregate_id=str(installation_id),
                        correlation_id=operation_id,
                        payload={
                            "artifact_id": str(artifact.id),
                            "release_id": str(release.id),
                            "target": request.target,
                        },
                    ),
                ]
            )
        return InstallationRecorded(
            installation_id=installation_id,
            operation_id=operation_id,
        )

    async def confirm_update(self, request: ConfirmUpdateInput) -> OperationStatus:
        async with self._sessions() as session, session.begin():
            operation = await session.scalar(
                select(CatalogDistributionOperation)
                .where(CatalogDistributionOperation.id == request.operation_id)
                .with_for_update()
            )
            if operation is None or operation.kind != "update":
                raise ToolError("operation_not_found")
            if operation.actor_id != request.actor_id:
                raise ToolError("operation_actor_mismatch")
            if operation.status == "succeeded":
                return OperationStatus(operation_id=operation.id, status="succeeded")
            if operation.status != "accepted" or operation.installation_id is None:
                raise ToolError("operation_not_actionable")
            installation = await session.scalar(
                select(CatalogInstallation)
                .where(CatalogInstallation.id == operation.installation_id)
                .with_for_update()
            )
            if installation is None:
                raise ToolError("installation_not_found")
            if installation.revision != request.expected_revision:
                raise ToolError("installation_revision_conflict")
            if installation.status != "active":
                raise ToolError("installation_not_active")
            if operation.release_id is None:
                raise ToolError("operation_release_missing")
            release_row = (
                await session.execute(
                    select(CatalogRelease, CatalogArtifactVersion)
                    .join(
                        CatalogArtifactVersion,
                        CatalogArtifactVersion.id == CatalogRelease.artifact_version_id,
                    )
                    .where(CatalogRelease.id == operation.release_id)
                )
            ).first()
            if release_row is None:
                raise ToolError("release_not_found")
            release, version = release_row
            if release.status != "published" or request.installed_digest != release.content_digest:
                raise ToolError("update_receipt_invalid")
            self._verify_release_integrity(release, version.content_digest)
            requirement = version.manifest.get("compatibility", {}).get(installation.profile)
            try:
                compatible = isinstance(requirement, str) and Version(
                    installation.client_version
                ) in SpecifierSet(requirement)
            except InvalidSpecifier, InvalidVersion:
                compatible = False
            if not compatible:
                raise ToolError("target_profile_incompatible")
            previous_release_id = installation.active_release_id
            installation.active_release_id = release.id
            installation.rollback_release_id = previous_release_id
            installation.revision += 1
            operation.status = "succeeded"
            operation.completed_at = datetime.now(UTC)
            operation.result = {"revision": installation.revision}
            session.add_all(
                [
                    CatalogInstallationHistory(
                        installation_id=installation.id,
                        sequence=installation.revision,
                        action="update",
                        from_release_id=previous_release_id,
                        to_release_id=release.id,
                        status="active",
                        actor_id=request.actor_id,
                    ),
                    OutboxEvent(
                        topic="artifact.updated",
                        aggregate_type="installation",
                        aggregate_id=str(installation.id),
                        correlation_id=operation.id,
                        payload={
                            "installation_id": str(installation.id),
                            "previous_release_id": str(previous_release_id),
                            "release_id": str(release.id),
                            "revision": installation.revision,
                        },
                    ),
                ]
            )
        return OperationStatus(operation_id=operation.id, status="succeeded")

    async def get_operation(self, request: GetOperationInput) -> OperationStatus:
        async with self._sessions() as session:
            operation = await session.get(CatalogDistributionOperation, request.operation_id)
        if operation is None:
            raise ToolError("operation_not_found")
        return OperationStatus(
            operation_id=operation.id,
            status=operation.status,
            error_code=operation.error_code,
        )

    async def manage_installation(self, request: ManageInstallationInput) -> OperationStatus:
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "installation_id": str(request.installation_id),
                    "action": request.action.value,
                    "expected_revision": request.expected_revision,
                    "reason": request.reason,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with self._sessions() as session, session.begin():
            existing = await session.scalar(
                select(CatalogDistributionOperation).where(
                    CatalogDistributionOperation.actor_id == request.actor_id,
                    CatalogDistributionOperation.idempotency_key == request.idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ToolError("idempotency_key_conflict")
                return OperationStatus(
                    operation_id=existing.id,
                    status=existing.status,
                    error_code=existing.error_code,
                )
            installation = await session.scalar(
                select(CatalogInstallation)
                .where(CatalogInstallation.id == request.installation_id)
                .with_for_update()
            )
            if installation is None:
                raise ToolError("installation_not_found")
            if installation.revision != request.expected_revision:
                raise ToolError("installation_revision_conflict")
            previous_release_id = installation.active_release_id
            if request.action.value == "rollback":
                if installation.rollback_release_id is None:
                    raise ToolError("rollback_release_unavailable")
                rollback_release = await session.get(
                    CatalogRelease, installation.rollback_release_id
                )
                if rollback_release is None or rollback_release.status != "published":
                    raise ToolError("rollback_release_unavailable")
                installation.active_release_id = rollback_release.id
                installation.rollback_release_id = previous_release_id
                installation.status = "active"
                operation_status = "rolled-back"
            elif request.action.value == "suspend":
                if installation.status == "revoked":
                    raise ToolError("installation_revoked")
                installation.status = "suspended"
                operation_status = "succeeded"
            elif request.action.value == "resume":
                if installation.status == "revoked":
                    raise ToolError("installation_revoked")
                installation.status = "active"
                operation_status = "succeeded"
            else:
                installation.status = "revoked"
                operation_status = "succeeded"
            installation.revision += 1
            operation_id = uuid7()
            now = datetime.now(UTC)
            session.add_all(
                [
                    CatalogInstallationHistory(
                        installation_id=installation.id,
                        sequence=installation.revision,
                        action=request.action.value,
                        from_release_id=previous_release_id,
                        to_release_id=installation.active_release_id,
                        status=installation.status,
                        actor_id=request.actor_id,
                        reason=request.reason,
                    ),
                    CatalogDistributionOperation(
                        id=operation_id,
                        installation_id=installation.id,
                        release_id=installation.active_release_id,
                        kind=request.action.value,
                        status=operation_status,
                        actor_id=request.actor_id,
                        idempotency_key=request.idempotency_key,
                        request_hash=request_hash,
                        result={"revision": installation.revision},
                        completed_at=now,
                    ),
                    OutboxEvent(
                        topic=f"artifact.installation.{request.action.value}",
                        aggregate_type="installation",
                        aggregate_id=str(installation.id),
                        correlation_id=operation_id,
                        payload={
                            "installation_id": str(installation.id),
                            "release_id": str(installation.active_release_id),
                            "status": installation.status,
                            "revision": installation.revision,
                        },
                    ),
                ]
            )
        return OperationStatus(operation_id=operation_id, status=operation_status)

    async def publish_candidate(self, request: PublishCandidateInput) -> PublicationAccepted:
        raise ToolError("tool_not_implemented")

    def _verify_release_integrity(
        self,
        release: CatalogRelease,
        version_digest: str,
    ) -> None:
        if self._trust_store is None:
            raise ToolError("installation_trust_unavailable")
        if release.content_digest != version_digest:
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

    @staticmethod
    def _latest_compatible_candidate(
        installation: CatalogInstallation,
        current: CatalogArtifactVersion,
        candidates: list[tuple[CatalogRelease, CatalogArtifactVersion]],
    ) -> tuple[CatalogRelease, CatalogArtifactVersion, UpdateDecision] | None:
        try:
            current_version = Version(current.version)
            client_version = Version(installation.client_version)
        except InvalidVersion:
            return None
        compatible: list[tuple[Version, CatalogRelease, CatalogArtifactVersion]] = []
        for release, version in candidates:
            requirement = version.manifest.get("compatibility", {}).get(installation.profile)
            try:
                if not isinstance(requirement, str):
                    continue
                if client_version not in SpecifierSet(requirement):
                    continue
                candidate_version = Version(version.version)
            except InvalidSpecifier, InvalidVersion:
                continue
            if candidate_version > current_version:
                compatible.append((candidate_version, release, version))
        if not compatible:
            return None
        candidate_version, release, version = max(compatible, key=lambda item: item[0])
        if candidate_version.major != current_version.major:
            kind = ChangeKind.MAJOR
        elif candidate_version.minor != current_version.minor:
            kind = ChangeKind.MINOR
        else:
            kind = ChangeKind.PATCH
        decision = assess_update(UpdatePolicy(), kind=kind, is_compatible=True)
        return release, version, decision


__all__ = ["SqlAlchemyRegistryMcpBackend"]
