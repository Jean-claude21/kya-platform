"""Daily, idempotent assessment of available artifact updates."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from kya_platform.domain.distribution import (
    ChangeKind,
    UpdateDecision,
    UpdatePolicy,
    assess_update,
)


@dataclass(frozen=True, slots=True)
class UpdateCandidate:
    installation_id: UUID
    current_release_id: UUID
    candidate_release_id: UUID
    kind: ChangeKind
    is_compatible: bool
    policy: UpdatePolicy


@dataclass(frozen=True, slots=True)
class UpdateAssessment:
    installation_id: UUID
    current_release_id: UUID
    candidate_release_id: UUID
    decision: UpdateDecision
    assessed_at: datetime


class UpdateAssessmentPort(Protocol):
    async def candidates(self) -> tuple[UpdateCandidate, ...]: ...

    async def exists(self, installation_id: UUID, candidate_release_id: UUID) -> bool: ...

    async def record(self, assessment: UpdateAssessment) -> None: ...


@dataclass(frozen=True, slots=True)
class UpdateJobResult:
    assessed: int
    skipped: int
    blocked: int


class DailyUpdateAssessmentJob:
    """Classify changes; never installs a release as an implicit side effect."""

    def __init__(self, assessments: UpdateAssessmentPort) -> None:
        self._assessments = assessments

    async def run(self, *, now: datetime | None = None) -> UpdateJobResult:
        assessed = skipped = blocked = 0
        assessed_at = now or datetime.now(UTC)
        if assessed_at.tzinfo is None:
            raise ValueError("assessment time must be timezone-aware")

        for candidate in await self._assessments.candidates():
            if candidate.current_release_id == candidate.candidate_release_id:
                skipped += 1
                continue
            if await self._assessments.exists(
                candidate.installation_id, candidate.candidate_release_id
            ):
                skipped += 1
                continue
            decision = assess_update(
                candidate.policy,
                kind=candidate.kind,
                is_compatible=candidate.is_compatible,
            )
            await self._assessments.record(
                UpdateAssessment(
                    candidate.installation_id,
                    candidate.current_release_id,
                    candidate.candidate_release_id,
                    decision,
                    assessed_at,
                )
            )
            assessed += 1
            blocked += decision is UpdateDecision.BLOCK
        return UpdateJobResult(assessed, skipped, blocked)


__all__ = [
    "DailyUpdateAssessmentJob",
    "UpdateAssessment",
    "UpdateAssessmentPort",
    "UpdateCandidate",
    "UpdateJobResult",
]
