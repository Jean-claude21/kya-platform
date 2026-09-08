"""Automatic watch evaluation is scoped, selective and replay safe."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest

from kya_platform.application.intelligence import IntelligenceService
from kya_platform.domain.intelligence import IntelligenceWatch, WatchEvaluation, WatchStatus
from kya_platform.workers.intelligence_evaluation import IntelligenceEvaluationWorker

ACTOR = UUID("019934b0-0000-7000-8000-000000000001")
RUN = UUID("019934b0-0000-7000-8000-000000000002")
CORRELATION = UUID("019934b0-0000-7000-8000-000000000003")
UNIT = UUID("019934b0-0000-7000-8000-000000000004")
ACTIVE = UUID("019934b0-0000-7000-8000-000000000005")
PAUSED = UUID("019934b0-0000-7000-8000-000000000006")


class Service:
    commands: list[object]

    def __init__(self) -> None:
        now = datetime(2026, 9, 8, tzinfo=UTC)
        self.watches = (
            IntelligenceWatch(
                ACTIVE,
                "solar",
                "Solar",
                "solaire",
                UNIT,
                ACTOR,
                (),
                WatchStatus.ACTIVE,
                2,
                now,
                now,
            ),
            IntelligenceWatch(
                PAUSED,
                "paused",
                "Paused",
                "veille",
                UNIT,
                ACTOR,
                (),
                WatchStatus.PAUSED,
                1,
                now,
                now,
            ),
        )
        self.commands = []

    async def list_watches(self, unit_key: str, *, limit: int) -> tuple[IntelligenceWatch, ...]:
        assert unit_key == "group"
        assert limit == 100
        return self.watches

    async def evaluate_watch(
        self, unit_key: str, watch_key: str, *, limit: int, command: object
    ) -> WatchEvaluation:
        assert unit_key == "group"
        assert watch_key == "solar"
        assert limit == 50
        self.commands.append(command)
        return WatchEvaluation(self.watches[0], (), 0)


@pytest.mark.asyncio
async def test_evaluates_only_active_watches_with_stable_command_identity() -> None:
    service = Service()
    worker = IntelligenceEvaluationWorker(cast(IntelligenceService, service))
    payload = {
        "aggregate_id": str(RUN),
        "unit_key": "group",
        "actor_id": str(ACTOR),
        "correlation_id": str(CORRELATION),
    }

    await worker.handle(payload)
    await worker.handle(payload)

    assert len(service.commands) == 2
    first, second = service.commands
    assert first.actor_id == ACTOR
    assert first.correlation_id == CORRELATION
    assert first.idempotency_key == f"auto-evaluate:{RUN}:{ACTIVE}"
    assert first.request_hash == second.request_hash


@pytest.mark.asyncio
async def test_rejects_incomplete_event_payload() -> None:
    worker = IntelligenceEvaluationWorker(cast(IntelligenceService, Service()))
    with pytest.raises(ValueError, match="unit_key"):
        await worker.handle({"aggregate_id": str(RUN)})


def test_rejects_invalid_evaluation_limit() -> None:
    with pytest.raises(ValueError, match="evaluation limit"):
        IntelligenceEvaluationWorker(cast(IntelligenceService, Service()), evaluation_limit=0)
