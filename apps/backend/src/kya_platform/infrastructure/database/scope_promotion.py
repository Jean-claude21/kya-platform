"""Neon adapter for scope promotion; applying it widens the artifact's live scope."""

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application import OutboxMessage
from kya_platform.domain.catalog import (
    Approval,
    ApprovalDecision,
    Review,
    ReviewDecision,
    ScopePromotionRequest,
    ScopePromotionStatus,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogScopePromotion,
    OutboxEvent,
)


def _domain(row: CatalogScopePromotion) -> ScopePromotionRequest:
    review = None
    if row.reviewer_id and row.review_decision and row.reviewed_at:
        review = Review(row.reviewer_id, ReviewDecision(row.review_decision), row.reviewed_at)
    approval = None
    if row.approver_id and row.approval_decision and row.approved_at:
        approval = Approval(
            row.approver_id, ApprovalDecision(row.approval_decision), row.approved_at
        )
    return ScopePromotionRequest(
        id=row.id,
        artifact_id=row.artifact_id,
        current_scope_unit_id=row.current_scope_unit_id,
        target_scope_unit_id=row.target_scope_unit_id,
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        separation_of_duties=row.separation_of_duties,
        status=ScopePromotionStatus(row.status),
        review_record=review,
        approval=approval,
        applied_by=row.applied_by,
        applied_at=row.applied_at,
    )


class SqlAlchemyScopePromotionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, request_id: UUID) -> ScopePromotionRequest | None:
        row = await self._session.scalar(
            select(CatalogScopePromotion)
            .where(CatalogScopePromotion.id == request_id)
            .with_for_update()
        )
        return _domain(row) if row is not None else None

    async def save(self, request: ScopePromotionRequest) -> None:
        row = await self._session.scalar(
            select(CatalogScopePromotion)
            .where(CatalogScopePromotion.id == request.id)
            .with_for_update()
        )
        if row is None:
            self._session.add(
                CatalogScopePromotion(
                    id=request.id,
                    artifact_id=request.artifact_id,
                    current_scope_unit_id=request.current_scope_unit_id,
                    target_scope_unit_id=request.target_scope_unit_id,
                    requested_by=request.requested_by,
                    requested_at=request.requested_at,
                    separation_of_duties=request.separation_of_duties,
                    status=request.status.value,
                )
            )
            return
        was_applied = row.status == ScopePromotionStatus.APPLIED.value
        row.status = request.status.value
        row.reviewer_id = request.review_record.reviewer_id if request.review_record else None
        row.review_decision = (
            request.review_record.decision.value if request.review_record else None
        )
        row.reviewed_at = request.review_record.reviewed_at if request.review_record else None
        row.approver_id = request.approval.approver_id if request.approval else None
        row.approval_decision = request.approval.decision.value if request.approval else None
        row.approved_at = request.approval.approved_at if request.approval else None
        row.applied_by = request.applied_by
        row.applied_at = request.applied_at
        if request.status is ScopePromotionStatus.APPLIED and not was_applied:
            await self._widen_artifact_scope(row)

    async def _widen_artifact_scope(self, row: CatalogScopePromotion) -> None:
        artifact = await self._session.get(CatalogArtifact, row.artifact_id)
        if artifact is None:
            raise ValueError("scope promotion target artifact disappeared")
        artifact.visibility_scope_unit_id = row.target_scope_unit_id


class SqlAlchemyScopePromotionOutbox:
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


class SqlAlchemyScopePromotionUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None
        self.promotions: SqlAlchemyScopePromotionRepository
        self.outbox: SqlAlchemyScopePromotionOutbox

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        await self._session.begin()
        self.promotions = SqlAlchemyScopePromotionRepository(self._session)
        self.outbox = SqlAlchemyScopePromotionOutbox(self._session)
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
            raise RuntimeError("scope promotion unit of work is not active")
        await self._session.commit()


__all__ = [
    "SqlAlchemyScopePromotionOutbox",
    "SqlAlchemyScopePromotionRepository",
    "SqlAlchemyScopePromotionUnitOfWork",
]
