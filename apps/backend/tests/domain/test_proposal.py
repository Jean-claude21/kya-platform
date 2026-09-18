"""Non-developer contribution lifecycle: a proposal never bypasses human review."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.catalog import ArtifactType, Proposal, ProposalStatus

AUTHOR = UUID("019914b2-1a40-7000-8000-000000000031")
REVIEWER = UUID("019914b2-1a40-7000-8000-000000000032")
BUSINESS_OWNER = UUID("019914b2-1a40-7000-8000-000000000041")
TECHNICAL_OWNER = UUID("019914b2-1a40-7000-8000-000000000042")
WORKSPACE = UUID("019914b2-1a40-7000-8000-000000000071")
PROPOSAL = UUID("019914b2-1a40-7000-8000-0000000000c1")
NOW = datetime(2026, 9, 11, tzinfo=UTC)


def opened() -> Proposal:
    return Proposal.open(
        id=PROPOSAL,
        target_workspace_id=WORKSPACE,
        slug="solar-brief",
        artifact_type=ArtifactType.SKILL,
        artifact_id=None,
        requested_by=AUTHOR,
        requested_at=NOW,
    )


@pytest.mark.unit
def test_open_proposal_starts_submitted_without_any_git_reference() -> None:
    proposal = opened()

    assert proposal.status is ProposalStatus.SUBMITTED
    assert proposal.merged_commit_sha is None
    assert proposal.pull_request_url is None


@pytest.mark.unit
def test_author_cannot_approve_or_reject_own_proposal() -> None:
    proposal = opened()

    with pytest.raises(PermissionError, match="approve own"):
        proposal.approve(
            AUTHOR,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
        )
    with pytest.raises(PermissionError, match="reject own"):
        proposal.reject(AUTHOR, reason="not needed", at=NOW)


@pytest.mark.unit
def test_principal_administrator_override_is_explicitly_recorded() -> None:
    proposal = opened()

    approved = proposal.approve(
        AUTHOR,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        administrative_override=True,
        at=NOW,
    )

    assert approved.status is ProposalStatus.APPROVED
    assert approved.reviewer_id == AUTHOR
    assert approved.administrative_override_by == AUTHOR


@pytest.mark.unit
def test_approval_assigns_ownership_the_author_never_receives_automatically() -> None:
    proposal = opened()

    approved = proposal.approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )

    assert approved.status is ProposalStatus.APPROVED
    assert approved.business_owner_id == BUSINESS_OWNER
    assert approved.technical_owner_id == TECHNICAL_OWNER
    assert approved.requested_by == AUTHOR


@pytest.mark.unit
def test_rejection_is_terminal_and_records_a_reason() -> None:
    proposal = opened()

    rejected = proposal.reject(REVIEWER, reason="duplicate of an existing Skill", at=NOW)

    assert rejected.status is ProposalStatus.REJECTED
    assert rejected.review_reason == "duplicate of an existing Skill"
    with pytest.raises(ValueError, match="awaiting a review decision"):
        rejected.approve(
            REVIEWER,
            business_owner_id=BUSINESS_OWNER,
            technical_owner_id=TECHNICAL_OWNER,
            at=NOW,
        )


@pytest.mark.unit
def test_a_pull_request_can_only_follow_an_approved_proposal() -> None:
    proposal = opened()

    with pytest.raises(ValueError, match="approved proposal"):
        proposal.mark_pull_request_open(pull_request_url="https://github.com/kya/pr/1")

    approved = proposal.approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )
    opened_pr = approved.mark_pull_request_open(pull_request_url="https://github.com/kya/pr/1")
    assert opened_pr.status is ProposalStatus.PULL_REQUEST_OPEN
    assert opened_pr.pull_request_url == "https://github.com/kya/pr/1"


@pytest.mark.unit
def test_merge_requires_a_real_commit_sha_and_produces_a_version_reference() -> None:
    approved = opened().approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )
    opened_pr = approved.mark_pull_request_open(pull_request_url="https://github.com/kya/pr/1")

    with pytest.raises(ValueError, match="40-character"):
        opened_pr.mark_merged(commit_sha="too-short", resulting_artifact_version_id=PROPOSAL)

    merged = opened_pr.mark_merged(commit_sha="a" * 40, resulting_artifact_version_id=PROPOSAL)
    assert merged.status is ProposalStatus.MERGED
    assert merged.merged_commit_sha == "a" * 40
    assert merged.resulting_artifact_version_id == PROPOSAL


@pytest.mark.unit
def test_closing_without_merge_is_terminal() -> None:
    approved = opened().approve(
        REVIEWER,
        business_owner_id=BUSINESS_OWNER,
        technical_owner_id=TECHNICAL_OWNER,
        at=NOW,
    )
    opened_pr = approved.mark_pull_request_open(pull_request_url="https://github.com/kya/pr/1")

    closed = opened_pr.mark_closed_without_merge()

    assert closed.status is ProposalStatus.CLOSED_WITHOUT_MERGE
    with pytest.raises(ValueError, match="open pull request"):
        closed.mark_merged(commit_sha="a" * 40, resulting_artifact_version_id=PROPOSAL)
