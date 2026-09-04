"""Artifact lifecycle and separation-of-duty publication rules."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.catalog import (
    ApprovalDecision,
    Artifact,
    ArtifactLifecycle,
    ArtifactType,
    ArtifactVersion,
    PublicationRequest,
    PublicationStatus,
    ReviewDecision,
)

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
APPROVER = UUID("019914b2-1a40-7000-8000-000000000033")
ARTIFACT = UUID("019914b2-1a40-7000-8000-0000000000a1")
WORKSPACE = UUID("019914b2-1a40-7000-8000-000000000071")
NOW = datetime(2026, 9, 4, tzinfo=UTC)


def candidate() -> ArtifactVersion:
    return ArtifactVersion(
        artifact_id=ARTIFACT,
        version="1.0.0",
        commit_sha="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
    )


@pytest.mark.unit
def test_artifact_lifecycle_rejects_skipped_and_backward_transitions() -> None:
    artifact = Artifact(
        id=ARTIFACT,
        slug="communication-document-format",
        artifact_type=ArtifactType.SKILL,
        name="Format documentaire KYA",
        owner_workspace_id=WORKSPACE,
        business_owner_id=AUTHOR,
        technical_owner_id=REVIEWER,
    )

    with pytest.raises(ValueError, match="transition"):
        artifact.transition_to(ArtifactLifecycle.PUBLISHED)

    prototype = artifact.transition_to(ArtifactLifecycle.PROTOTYPE)
    assert prototype.lifecycle is ArtifactLifecycle.PROTOTYPE
    with pytest.raises(ValueError, match="transition"):
        prototype.transition_to(ArtifactLifecycle.DRAFT)


@pytest.mark.unit
def test_candidate_version_is_immutable_and_content_addressed() -> None:
    version = candidate()

    with pytest.raises(AttributeError):
        version.version = "2.0.0"  # type: ignore[misc]
    with pytest.raises(ValueError, match="commit"):
        ArtifactVersion(ARTIFACT, "1.0.0", "short", "b" * 64, "c" * 64)


@pytest.mark.unit
def test_author_cannot_review_or_approve_own_request() -> None:
    request = PublicationRequest.open(
        id=UUID("019914b2-1a40-7000-8000-0000000000b1"),
        candidate=candidate(),
        requested_by=AUTHOR,
        requested_at=NOW,
        separation_of_duties=True,
    )

    with pytest.raises(PermissionError, match="review own"):
        request.review(AUTHOR, ReviewDecision.ACCEPTED, at=NOW)
    reviewed = request.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW)
    with pytest.raises(PermissionError, match="approve own"):
        reviewed.approve(AUTHOR, ApprovalDecision.APPROVED, at=NOW)
    with pytest.raises(PermissionError, match="reviewer cannot approve"):
        reviewed.approve(REVIEWER, ApprovalDecision.APPROVED, at=NOW)


@pytest.mark.unit
def test_approval_requires_an_accepted_review_and_preserves_candidate_digest() -> None:
    request = PublicationRequest.open(
        id=UUID("019914b2-1a40-7000-8000-0000000000b2"),
        candidate=candidate(),
        requested_by=AUTHOR,
        requested_at=NOW,
        separation_of_duties=True,
    )

    with pytest.raises(ValueError, match="accepted review"):
        request.approve(APPROVER, ApprovalDecision.APPROVED, at=NOW)

    approved = request.review(REVIEWER, ReviewDecision.ACCEPTED, at=NOW).approve(
        APPROVER, ApprovalDecision.APPROVED, at=NOW
    )
    assert approved.status is PublicationStatus.APPROVED
    assert approved.candidate.content_digest == "b" * 64
    assert approved.approval is not None


@pytest.mark.unit
def test_rejection_is_terminal_for_the_frozen_candidate() -> None:
    request = PublicationRequest.open(
        id=UUID("019914b2-1a40-7000-8000-0000000000b3"),
        candidate=candidate(),
        requested_by=AUTHOR,
        requested_at=NOW,
        separation_of_duties=False,
    )
    rejected = request.review(REVIEWER, ReviewDecision.REJECTED, at=NOW)

    assert rejected.status is PublicationStatus.REJECTED
    with pytest.raises(ValueError, match="awaiting review"):
        rejected.review(APPROVER, ReviewDecision.ACCEPTED, at=NOW)
