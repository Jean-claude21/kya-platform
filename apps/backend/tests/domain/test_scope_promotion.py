"""Scope promotion widens visibility with the same separation-of-duty rules."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.catalog import (
    ApprovalDecision,
    ReviewDecision,
    ScopePromotionRequest,
    ScopePromotionStatus,
)

ARTIFACT = UUID("019914b2-1a40-7000-8000-0000000000d1")
AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
APPROVER = UUID("019914b2-1a40-7000-8000-000000000033")
TEAM_UNIT = UUID("019914b2-1a40-7000-8000-0000000000e1")
GROUP_UNIT = UUID("019914b2-1a40-7000-8000-0000000000e2")
REQUEST = UUID("019914b2-1a40-7000-8000-0000000000f1")
NOW = datetime(2026, 9, 12, tzinfo=UTC)


def opened() -> ScopePromotionRequest:
    return ScopePromotionRequest.open(
        id=REQUEST,
        artifact_id=ARTIFACT,
        current_scope_unit_id=TEAM_UNIT,
        target_scope_unit_id=GROUP_UNIT,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


@pytest.mark.unit
def test_open_promotion_starts_awaiting_review() -> None:
    request = opened()

    assert request.status is ScopePromotionStatus.AWAITING_REVIEW
    assert request.current_scope_unit_id == TEAM_UNIT
    assert request.target_scope_unit_id == GROUP_UNIT


@pytest.mark.unit
def test_author_cannot_review_or_approve_own_promotion() -> None:
    request = opened()

    with pytest.raises(PermissionError, match="review own"):
        request.review(AUTHOR, ReviewDecision.ACCEPTED, at=NOW)
    reviewed = request.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
    with pytest.raises(PermissionError, match="approve own"):
        reviewed.approve(AUTHOR, ApprovalDecision.APPROVED, at=NOW)
    with pytest.raises(PermissionError, match="reviewer cannot approve"):
        reviewed.approve(REVIEWER, ApprovalDecision.APPROVED, at=NOW)


@pytest.mark.unit
def test_approval_requires_an_accepted_review() -> None:
    request = opened()

    with pytest.raises(ValueError, match="accepted review"):
        request.approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)

    approved = request.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW).approve(
        APPROVER, ApprovalDecision.APPROVED, at=NOW
    )
    assert approved.status is ScopePromotionStatus.APPROVED


@pytest.mark.unit
def test_apply_requires_approval_and_records_who_applied_it() -> None:
    request = opened()

    with pytest.raises(ValueError, match="approved scope promotion"):
        request.apply(APPROVER, at=NOW)

    applied = (
        request.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
        .approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)
        .apply(APPROVER, at=NOW)
    )
    assert applied.status is ScopePromotionStatus.APPLIED
    assert applied.applied_by == APPROVER
    assert applied.applied_at == NOW


@pytest.mark.unit
def test_rejection_is_terminal() -> None:
    request = opened()

    rejected = request.review(REVIEWER, ReviewDecision.REJECTED, at=NOW)

    assert rejected.status is ScopePromotionStatus.REJECTED
    with pytest.raises(ValueError, match="awaiting review"):
        rejected.review(APPROVER, ReviewDecision.ACCEPTED, at=NOW)
