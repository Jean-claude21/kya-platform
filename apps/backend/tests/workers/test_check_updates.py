from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from kya_platform.domain.distribution import ChangeKind, UpdateDecision, UpdatePolicy
from kya_platform.workers.check_updates import (
    DailyUpdateAssessmentJob,
    UpdateAssessment,
    UpdateCandidate,
)


@dataclass
class MemoryAssessments:
    available: tuple[UpdateCandidate, ...]
    recorded: list[UpdateAssessment] = field(default_factory=list)

    async def candidates(self) -> tuple[UpdateCandidate, ...]:
        return self.available

    async def exists(self, installation_id: UUID, candidate_release_id: UUID) -> bool:
        return any(
            item.installation_id == installation_id
            and item.candidate_release_id == candidate_release_id
            for item in self.recorded
        )

    async def record(self, assessment: UpdateAssessment) -> None:
        self.recorded.append(assessment)


def candidate(*, compatible: bool = True) -> UpdateCandidate:
    return UpdateCandidate(
        installation_id=uuid4(),
        current_release_id=uuid4(),
        candidate_release_id=uuid4(),
        kind=ChangeKind.PATCH,
        is_compatible=compatible,
        policy=UpdatePolicy(),
    )


@pytest.mark.asyncio
async def test_daily_job_records_a_proposal_without_installing_anything() -> None:
    port = MemoryAssessments((candidate(),))
    now = datetime(2026, 9, 4, 6, tzinfo=UTC)

    result = await DailyUpdateAssessmentJob(port).run(now=now)

    assert result.assessed == 1
    assert port.recorded[0].decision is UpdateDecision.PROPOSE
    assert port.recorded[0].assessed_at == now


@pytest.mark.asyncio
async def test_daily_job_is_idempotent_for_installation_and_release() -> None:
    update = candidate()
    port = MemoryAssessments((update,))
    job = DailyUpdateAssessmentJob(port)

    first = await job.run(now=datetime(2026, 9, 4, 6, tzinfo=UTC))
    second = await job.run(now=datetime(2026, 9, 5, 6, tzinfo=UTC))

    assert first.assessed == 1
    assert second.skipped == 1
    assert len(port.recorded) == 1


@pytest.mark.asyncio
async def test_incompatible_update_is_recorded_as_blocked() -> None:
    port = MemoryAssessments((candidate(compatible=False),))

    result = await DailyUpdateAssessmentJob(port).run(now=datetime(2026, 9, 4, 6, tzinfo=UTC))

    assert result.blocked == 1
    assert port.recorded[0].decision is UpdateDecision.BLOCK


@pytest.mark.asyncio
async def test_job_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await DailyUpdateAssessmentJob(MemoryAssessments(())).run(now=datetime(2026, 9, 4, 6))
