"""Evaluate active watchlists after a governed ingestion completes."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import IntelligenceService
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.domain.intelligence import WatchStatus


class IntelligenceEvaluationWorker:
    """Idempotent event handler; evidence remains attributable to the ingestion actor."""

    def __init__(self, service: IntelligenceService, *, evaluation_limit: int = 50) -> None:
        if not 1 <= evaluation_limit <= 50:
            raise ValueError("evaluation limit must be between 1 and 50")
        self._service = service
        self._evaluation_limit = evaluation_limit

    async def handle(self, payload: Mapping[str, object]) -> None:
        unit_key = self._required_text(payload, "unit_key")
        run_id = UUID(self._required_text(payload, "aggregate_id"))
        actor_id = UUID(self._required_text(payload, "actor_id"))
        correlation_id = UUID(self._required_text(payload, "correlation_id"))
        watches = await self._service.list_watches(unit_key, limit=100)
        for watch in watches:
            if watch.status is not WatchStatus.ACTIVE:
                continue
            command_payload: dict[str, JsonValue] = {
                "run_id": str(run_id),
                "watch_id": str(watch.id),
                "watch_revision": watch.revision,
            }
            await self._service.evaluate_watch(
                unit_key,
                watch.key,
                limit=self._evaluation_limit,
                command=CommandMetadata(
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    idempotency_key=f"auto-evaluate:{run_id}:{watch.id}",
                    request_hash=canonical_request_hash(command_payload),
                    expires_at=datetime.now(UTC) + timedelta(days=30),
                ),
            )

    @staticmethod
    def _required_text(payload: Mapping[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value


__all__ = ["IntelligenceEvaluationWorker"]
