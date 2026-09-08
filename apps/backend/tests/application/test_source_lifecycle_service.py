"""Source lifecycle use cases remain transport-independent."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from kya_platform.application.data import CommandMetadata
from kya_platform.application.source_lifecycle import SourceFlowStateError, SourceLifecycleService
from kya_platform.domain.data import DataStatus
from kya_platform.domain.source_lifecycle import IngestionSchedule

IDENTIFIER = UUID("019934d0-0000-7000-8000-000000000001")
NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)
COMMAND = CommandMetadata(IDENTIFIER, IDENTIFIER, "source-lifecycle-command", "a" * 64, NOW)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_delegates_health_transition_schedule_and_claim() -> None:
    repository = AsyncMock()
    repository.get_health.return_value = None
    repository.transition.return_value = "transitioned"
    repository.put_schedule.return_value = "scheduled"
    repository.claim_due_runs.return_value = ()
    service = SourceLifecycleService(repository)
    schedule = IngestionSchedule(IDENTIFIER, IDENTIFIER, 60, NOW)

    assert await service.get_health("group", "solar") is None
    assert (
        await service.transition(
            "group",
            "solar",
            DataStatus.PAUSED,
            expected_revision=1,
            command=COMMAND,
        )
        == "transitioned"
    )
    assert (
        await service.put_schedule("group", "solar", schedule, expected_revision=2, command=COMMAND)
        == "scheduled"
    )
    assert await service.claim_due_runs(now=NOW, limit=5) == ()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_rejects_unsupported_transition_and_claim_limit() -> None:
    service = SourceLifecycleService(AsyncMock())
    with pytest.raises(SourceFlowStateError, match="active and paused"):
        await service.transition(
            "group",
            "solar",
            DataStatus.RETIRED,
            expected_revision=1,
            command=COMMAND,
        )
    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.claim_due_runs(now=NOW, limit=0)
