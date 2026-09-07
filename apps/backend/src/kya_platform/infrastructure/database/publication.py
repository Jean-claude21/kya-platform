"""Transactional Neon unit of work for governed artifact publication."""

import hashlib
import json
from datetime import datetime
from types import TracebackType
from typing import Self
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application import OutboxMessage
from kya_platform.application.publication.evidence import (
    AttestationKind,
    AttestationRecord,
    required_attestation_kinds,
)
from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.domain.catalog import (
    Approval,
    ApprovalDecision,
    ArtifactVersion,
    PublicationRequest,
    PublicationStatus,
    Review,
    ReviewDecision,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogAttestation,
    CatalogPublicationRequest,
    CatalogRelease,
    OutboxEvent,
)


def _domain(row: CatalogPublicationRequest) -> PublicationRequest:
    review = None
    if row.reviewer_id and row.review_decision and row.reviewed_at:
        review = Review(row.reviewer_id, ReviewDecision(row.review_decision), row.reviewed_at)
    approval = None
    if row.approver_id and row.approval_decision and row.approved_at:
        approval = Approval(
            row.approver_id,
            ApprovalDecision(row.approval_decision),
            row.approved_at,
        )
    return PublicationRequest(
        id=row.id,
        candidate=ArtifactVersion(
            row.artifact_id,
            row.version,
            row.commit_sha,
            row.content_digest,
            row.manifest_digest,
        ),
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        separation_of_duties=row.separation_of_duties,
        status=PublicationStatus(row.status),
        evidence_ids=tuple(UUID(value) for value in row.evidence_ids),
        review_record=review,
        approval=approval,
        published_by=row.published_by,
        published_at=row.published_at,
    )


class SqlAlchemyPublicationRepository:
    def __init__(self, session: AsyncSession, signer: Ed25519ArtifactSigner) -> None:
        self._session = session
        self._signer = signer

    async def get(self, request_id: UUID) -> PublicationRequest | None:
        row = await self._session.scalar(
            select(CatalogPublicationRequest)
            .where(CatalogPublicationRequest.id == request_id)
            .with_for_update()
        )
        return _domain(row) if row is not None else None

    async def save(self, request: PublicationRequest) -> None:
        row = await self._session.scalar(
            select(CatalogPublicationRequest)
            .where(CatalogPublicationRequest.id == request.id)
            .with_for_update()
        )
        if row is None:
            await self._insert(request)
            return
        was_published = row.status == PublicationStatus.PUBLISHED.value
        self._update(row, request)
        if request.status is PublicationStatus.PUBLISHED and not was_published:
            await self._release(row, request)

    async def _insert(self, request: PublicationRequest) -> None:
        candidate = request.candidate
        version = await self._session.scalar(
            select(CatalogArtifactVersion).where(
                CatalogArtifactVersion.artifact_id == candidate.artifact_id,
                CatalogArtifactVersion.version == candidate.version,
                CatalogArtifactVersion.source_commit == candidate.commit_sha.lower(),
                CatalogArtifactVersion.content_digest == candidate.content_digest.lower(),
                CatalogArtifactVersion.manifest_digest == candidate.manifest_digest.lower(),
            )
        )
        if version is None:
            raise ValueError("publication candidate does not match a persisted artifact version")
        if not request.evidence_ids or len(request.evidence_ids) != len(set(request.evidence_ids)):
            raise ValueError("publication requires unique attestation evidence")
        attestations: list[CatalogAttestation] = []
        for evidence_id in request.evidence_ids:
            evidence = await self._session.get(CatalogAttestation, evidence_id)
            if evidence is None or evidence.artifact_version_id != version.id:
                raise ValueError("publication evidence does not belong to the candidate")
            if evidence.subject_digest != version.content_digest or evidence.result != "passed":
                raise ValueError("publication evidence did not pass for the candidate digest")
            if evidence.valid_from > request.requested_at or (
                evidence.valid_until is not None and evidence.valid_until <= request.requested_at
            ):
                raise ValueError("publication evidence is not currently valid")
            attestations.append(evidence)
        provided = {AttestationKind(item.kind) for item in attestations}
        required = required_attestation_kinds(
            risk=version.risk,
            has_executable_content=version.has_executable_content,
        )
        missing = sorted(item.value for item in required - provided)
        if missing:
            raise ValueError(f"publication evidence is incomplete: {', '.join(missing)}")
        self._session.add(
            CatalogPublicationRequest(
                id=request.id,
                artifact_id=candidate.artifact_id,
                artifact_version_id=version.id,
                version=candidate.version,
                commit_sha=candidate.commit_sha.lower(),
                content_digest=candidate.content_digest.lower(),
                manifest_digest=candidate.manifest_digest.lower(),
                requested_by=request.requested_by,
                requested_at=request.requested_at,
                separation_of_duties=request.separation_of_duties,
                evidence_ids=[str(item) for item in request.evidence_ids],
                status=request.status.value,
            )
        )

    @staticmethod
    def _update(row: CatalogPublicationRequest, request: PublicationRequest) -> None:
        if row.artifact_id != request.candidate.artifact_id:
            raise ValueError("publication request artifact cannot change")
        row.status = request.status.value
        row.reviewer_id = request.review_record.reviewer_id if request.review_record else None
        row.review_decision = (
            request.review_record.decision.value if request.review_record else None
        )
        row.reviewed_at = request.review_record.reviewed_at if request.review_record else None
        row.approver_id = request.approval.approver_id if request.approval else None
        row.approval_decision = request.approval.decision.value if request.approval else None
        row.approved_at = request.approval.approved_at if request.approval else None
        row.published_by = request.published_by
        row.published_at = request.published_at
        row.revision += 1

    async def _release(self, row: CatalogPublicationRequest, request: PublicationRequest) -> None:
        if request.published_at is None or request.published_by is None:
            raise ValueError("published request requires publisher evidence")
        version = await self._session.get(CatalogArtifactVersion, row.artifact_version_id)
        artifact = await self._session.get(CatalogArtifact, row.artifact_id)
        if version is None or artifact is None:
            raise ValueError("publication target disappeared")
        if version.status == "published":
            raise ValueError("artifact version is already published")
        signature = self._signer.sign(
            version.id,
            request.candidate.content_digest,
            signed_at=request.published_at,
        )
        locator = f"git+{version.source_repository}@{version.source_commit}"
        if version.source_path:
            locator = f"{locator}#{version.source_path}"
        self._session.add(
            CatalogRelease(
                id=uuid7(),
                artifact_version_id=version.id,
                content_digest=request.candidate.content_digest,
                signature=signature.model_dump(mode="json"),
                storage_locator=locator,
                status="published",
                published_at=request.published_at,
                published_by=request.published_by,
            )
        )
        version.status = "published"
        artifact.lifecycle = "published"


class SqlAlchemyOutbox:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: OutboxMessage) -> None:
        self._session.add(
            OutboxEvent(
                topic=message.topic,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                payload=dict(message.payload),
                correlation_id=message.correlation_id,
            )
        )


class SqlAlchemyAttestationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(
        self,
        *,
        artifact_id: UUID,
        version_id: UUID,
        kind: AttestationKind,
        issuer_id: UUID,
        result: str,
        valid_from: datetime,
        valid_until: datetime | None,
        evidence_uri: str,
        correlation_id: UUID,
    ) -> AttestationRecord:
        if valid_until is not None and valid_until <= valid_from:
            raise ValueError("attestation expiration must follow its validity start")
        if result not in {"passed", "failed"}:
            raise ValueError("attestation result is invalid")
        async with self._sessions() as session, session.begin():
            version = await session.scalar(
                select(CatalogArtifactVersion).where(
                    CatalogArtifactVersion.id == version_id,
                    CatalogArtifactVersion.artifact_id == artifact_id,
                )
            )
            if version is None:
                raise ValueError("attestation target version does not exist")
            statement = {
                "artifactVersionId": str(version.id),
                "evidenceUri": evidence_uri,
                "issuerId": str(issuer_id),
                "kind": kind.value,
                "result": result,
                "subjectDigest": version.content_digest,
                "validFrom": valid_from.isoformat(),
                "validUntil": valid_until.isoformat() if valid_until else None,
            }
            digest = hashlib.sha256(
                json.dumps(statement, separators=(",", ":"), sort_keys=True).encode()
            ).hexdigest()
            row = CatalogAttestation(
                id=uuid7(),
                artifact_version_id=version.id,
                kind=kind.value,
                predicate_type=f"https://schemas.kya.energy/attestation/{kind.value}/v1",
                digest=digest,
                issuer_id=issuer_id,
                subject_digest=version.content_digest,
                result=result,
                valid_from=valid_from,
                valid_until=valid_until,
                evidence_uri=evidence_uri,
            )
            session.add(row)
            session.add(
                OutboxEvent(
                    topic="artifact.attestation.recorded",
                    aggregate_type="artifact_version",
                    aggregate_id=str(version.id),
                    correlation_id=correlation_id,
                    payload={
                        "artifact_id": str(artifact_id),
                        "version_id": str(version.id),
                        "attestation_id": str(row.id),
                        "kind": kind.value,
                        "result": result,
                    },
                )
            )
        return AttestationRecord(
            id=row.id,
            artifact_version_id=row.artifact_version_id,
            kind=kind,
            issuer_id=issuer_id,
            subject_digest=row.subject_digest,
            result=result,
            valid_from=valid_from,
            valid_until=valid_until,
            evidence_uri=evidence_uri,
        )


class SqlAlchemyPublicationUnitOfWork:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        signer: Ed25519ArtifactSigner,
    ) -> None:
        self._sessions = sessions
        self._signer = signer
        self._session: AsyncSession | None = None
        self.publications: SqlAlchemyPublicationRepository
        self.outbox: SqlAlchemyOutbox

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        await self._session.begin()
        self.publications = SqlAlchemyPublicationRepository(self._session, self._signer)
        self.outbox = SqlAlchemyOutbox(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._session is not None:
            if self._session.in_transaction():
                await self._session.rollback()
            await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("publication unit of work is not active")
        await self._session.commit()


__all__ = [
    "SqlAlchemyAttestationRepository",
    "SqlAlchemyOutbox",
    "SqlAlchemyPublicationRepository",
    "SqlAlchemyPublicationUnitOfWork",
]
