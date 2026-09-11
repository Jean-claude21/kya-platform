"""Governed catalog artifacts, versions and publication decisions."""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
_SHA1 = re.compile(r"^[a-fA-F0-9]{40}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


class ArtifactType(StrEnum):
    SYSTEM = "system"
    APPLICATION = "app"
    API = "api"
    DATA_PRODUCT = "data-product"
    MCP_SERVER = "mcp-server"
    MCP_TOOL = "mcp-tool"
    SKILL = "skill"
    TEMPLATE = "template"
    MODEL = "model"
    DESIGN_SYSTEM = "design-system"
    CONNECTOR = "connector"
    POLICY = "policy"


class ArtifactLifecycle(StrEnum):
    DRAFT = "draft"
    PROTOTYPE = "prototype"
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


_TRANSITIONS = {
    ArtifactLifecycle.DRAFT: frozenset({ArtifactLifecycle.PROTOTYPE}),
    ArtifactLifecycle.PROTOTYPE: frozenset({ArtifactLifecycle.CANDIDATE}),
    ArtifactLifecycle.CANDIDATE: frozenset({ArtifactLifecycle.VALIDATING}),
    ArtifactLifecycle.VALIDATING: frozenset({ArtifactLifecycle.APPROVED}),
    ArtifactLifecycle.APPROVED: frozenset({ArtifactLifecycle.PUBLISHED}),
    ArtifactLifecycle.PUBLISHED: frozenset(
        {ArtifactLifecycle.SUSPENDED, ArtifactLifecycle.DEPRECATED}
    ),
    ArtifactLifecycle.SUSPENDED: frozenset(
        {ArtifactLifecycle.PUBLISHED, ArtifactLifecycle.DEPRECATED}
    ),
    ArtifactLifecycle.DEPRECATED: frozenset({ArtifactLifecycle.RETIRED}),
    ArtifactLifecycle.RETIRED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Artifact:
    id: UUID
    slug: str
    artifact_type: ArtifactType
    name: str
    owner_workspace_id: UUID
    business_owner_id: UUID
    technical_owner_id: UUID
    lifecycle: ArtifactLifecycle = ArtifactLifecycle.DRAFT

    def __post_init__(self) -> None:
        if _SLUG.fullmatch(self.slug) is None:
            raise ValueError("artifact slug must be a stable kebab-case identifier")
        if not self.name.strip():
            raise ValueError("artifact name is required")

    def transition_to(self, target: ArtifactLifecycle) -> Artifact:
        if target not in _TRANSITIONS[self.lifecycle]:
            raise ValueError(f"invalid artifact transition: {self.lifecycle} -> {target}")
        return replace(self, lifecycle=target)


@dataclass(frozen=True, slots=True)
class ArtifactVersion:
    artifact_id: UUID
    version: str
    commit_sha: str
    content_digest: str
    manifest_digest: str

    def __post_init__(self) -> None:
        if _SEMVER.fullmatch(self.version) is None:
            raise ValueError("version must follow SemVer")
        if _SHA1.fullmatch(self.commit_sha) is None:
            raise ValueError("commit_sha must contain a 40-character hexadecimal commit")
        if _SHA256.fullmatch(self.content_digest) is None:
            raise ValueError("content_digest must be a SHA-256 hexadecimal digest")
        if _SHA256.fullmatch(self.manifest_digest) is None:
            raise ValueError("manifest_digest must be a SHA-256 hexadecimal digest")


class ReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationStatus(StrEnum):
    AWAITING_REVIEW = "awaiting-review"
    AWAITING_APPROVAL = "awaiting-approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class Review:
    reviewer_id: UUID
    decision: ReviewDecision
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class Approval:
    approver_id: UUID
    decision: ApprovalDecision
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class PublicationRequest:
    id: UUID
    candidate: ArtifactVersion
    requested_by: UUID
    requested_at: datetime
    separation_of_duties: bool
    status: PublicationStatus
    evidence_ids: tuple[UUID, ...] = ()
    review_record: Review | None = None
    approval: Approval | None = None
    published_by: UUID | None = None
    published_at: datetime | None = None

    @classmethod
    def open(
        cls,
        *,
        id: UUID,
        candidate: ArtifactVersion,
        requested_by: UUID,
        requested_at: datetime,
        separation_of_duties: bool,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> PublicationRequest:
        return cls(
            id=id,
            candidate=candidate,
            requested_by=requested_by,
            requested_at=requested_at,
            separation_of_duties=separation_of_duties,
            status=PublicationStatus.AWAITING_REVIEW,
            evidence_ids=evidence_ids,
        )

    def review(
        self, reviewer_id: UUID, decision: ReviewDecision, *, at: datetime
    ) -> PublicationRequest:
        if self.status is not PublicationStatus.AWAITING_REVIEW:
            raise ValueError("publication request is not awaiting review")
        if self.separation_of_duties and reviewer_id == self.requested_by:
            raise PermissionError("an author cannot review own publication request")
        next_status = (
            PublicationStatus.AWAITING_APPROVAL
            if decision is ReviewDecision.ACCEPTED
            else PublicationStatus.REJECTED
        )
        return replace(
            self,
            status=next_status,
            review_record=Review(reviewer_id, decision, at),
        )

    def approve(
        self, approver_id: UUID, decision: ApprovalDecision, *, at: datetime
    ) -> PublicationRequest:
        if (
            self.status is not PublicationStatus.AWAITING_APPROVAL
            or self.review_record is None
            or self.review_record.decision is not ReviewDecision.ACCEPTED
        ):
            raise ValueError("publication approval requires an accepted review")
        if self.separation_of_duties and approver_id == self.requested_by:
            raise PermissionError("an author cannot approve own publication request")
        if self.separation_of_duties and approver_id == self.review_record.reviewer_id:
            raise PermissionError("a reviewer cannot approve the same publication request")
        next_status = (
            PublicationStatus.APPROVED
            if decision is ApprovalDecision.APPROVED
            else PublicationStatus.REJECTED
        )
        return replace(
            self,
            status=next_status,
            approval=Approval(approver_id, decision, at),
        )

    def mark_published(
        self,
        publisher_id: UUID,
        *,
        content_digest: str,
        at: datetime,
    ) -> PublicationRequest:
        if self.status is not PublicationStatus.APPROVED:
            raise ValueError("only an approved candidate can be published")
        if content_digest != self.candidate.content_digest:
            raise ValueError("published content digest differs from the approved candidate")
        return replace(
            self,
            status=PublicationStatus.PUBLISHED,
            published_by=publisher_id,
            published_at=at,
        )


class ProposalStatus(StrEnum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PULL_REQUEST_OPEN = "pull_request_open"
    MERGED = "merged"
    CLOSED_WITHOUT_MERGE = "closed_without_merge"


@dataclass(frozen=True, slots=True)
class Proposal:
    """A non-developer contribution; never a Git-backed artifact version until merged."""

    id: UUID
    target_workspace_id: UUID
    slug: str
    artifact_type: ArtifactType
    artifact_id: UUID | None
    requested_by: UUID
    requested_at: datetime
    status: ProposalStatus = ProposalStatus.SUBMITTED
    reviewer_id: UUID | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None
    business_owner_id: UUID | None = None
    technical_owner_id: UUID | None = None
    pull_request_url: str | None = None
    merged_commit_sha: str | None = None
    resulting_artifact_version_id: UUID | None = None

    def __post_init__(self) -> None:
        if _SLUG.fullmatch(self.slug) is None:
            raise ValueError("proposal slug must be a stable kebab-case identifier")

    @classmethod
    def open(
        cls,
        *,
        id: UUID,
        target_workspace_id: UUID,
        slug: str,
        artifact_type: ArtifactType,
        artifact_id: UUID | None,
        requested_by: UUID,
        requested_at: datetime,
    ) -> Proposal:
        return cls(
            id=id,
            target_workspace_id=target_workspace_id,
            slug=slug,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            requested_by=requested_by,
            requested_at=requested_at,
            status=ProposalStatus.SUBMITTED,
        )

    def approve(
        self,
        reviewer_id: UUID,
        *,
        business_owner_id: UUID,
        technical_owner_id: UUID,
        at: datetime,
    ) -> Proposal:
        if self.status not in {ProposalStatus.SUBMITTED, ProposalStatus.IN_REVIEW}:
            raise ValueError("proposal is not awaiting a review decision")
        if reviewer_id == self.requested_by:
            raise PermissionError("an author cannot approve own proposal")
        return replace(
            self,
            status=ProposalStatus.APPROVED,
            reviewer_id=reviewer_id,
            reviewed_at=at,
            business_owner_id=business_owner_id,
            technical_owner_id=technical_owner_id,
        )

    def reject(self, reviewer_id: UUID, *, reason: str, at: datetime) -> Proposal:
        if self.status not in {ProposalStatus.SUBMITTED, ProposalStatus.IN_REVIEW}:
            raise ValueError("proposal is not awaiting a review decision")
        if reviewer_id == self.requested_by:
            raise PermissionError("an author cannot reject own proposal")
        return replace(
            self,
            status=ProposalStatus.REJECTED,
            reviewer_id=reviewer_id,
            review_reason=reason,
            reviewed_at=at,
        )

    def mark_pull_request_open(self, *, pull_request_url: str) -> Proposal:
        if self.status is not ProposalStatus.APPROVED:
            raise ValueError("a pull request can only follow an approved proposal")
        return replace(
            self, status=ProposalStatus.PULL_REQUEST_OPEN, pull_request_url=pull_request_url
        )

    def mark_merged(self, *, commit_sha: str, resulting_artifact_version_id: UUID) -> Proposal:
        if self.status is not ProposalStatus.PULL_REQUEST_OPEN:
            raise ValueError("only an open pull request can be marked merged")
        if _SHA1.fullmatch(commit_sha) is None:
            raise ValueError("merged_commit_sha must contain a 40-character hexadecimal commit")
        return replace(
            self,
            status=ProposalStatus.MERGED,
            merged_commit_sha=commit_sha,
            resulting_artifact_version_id=resulting_artifact_version_id,
        )

    def mark_closed_without_merge(self) -> Proposal:
        if self.status is not ProposalStatus.PULL_REQUEST_OPEN:
            raise ValueError("only an open pull request can close without merging")
        return replace(self, status=ProposalStatus.CLOSED_WITHOUT_MERGE)


__all__ = [
    "Approval",
    "ApprovalDecision",
    "Artifact",
    "ArtifactLifecycle",
    "ArtifactType",
    "ArtifactVersion",
    "Proposal",
    "ProposalStatus",
    "PublicationRequest",
    "PublicationStatus",
    "Review",
    "ReviewDecision",
]
