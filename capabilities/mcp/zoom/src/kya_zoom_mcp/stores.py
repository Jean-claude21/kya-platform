"""Development stores; production replaces them with a shared operation store."""

from __future__ import annotations

import asyncio

from kya_zoom_mcp.contracts import CreateMeetingResult, MeetingPlan


class MemoryMeetingPlanStore:
    def __init__(self) -> None:
        self._plans: dict[str, MeetingPlan] = {}
        self._lock = asyncio.Lock()

    async def put(self, plan: MeetingPlan) -> None:
        async with self._lock:
            self._plans[str(plan.plan_id)] = plan

    async def get(self, plan_id: str) -> MeetingPlan | None:
        async with self._lock:
            return self._plans.get(plan_id)


class MemoryOperationStore:
    def __init__(self) -> None:
        self._results: dict[tuple[str, str], CreateMeetingResult] = {}
        self._lock = asyncio.Lock()

    async def get(self, principal_id: str, idempotency_key: str) -> CreateMeetingResult | None:
        async with self._lock:
            return self._results.get((principal_id, idempotency_key))

    async def put(
        self, principal_id: str, idempotency_key: str, result: CreateMeetingResult
    ) -> None:
        async with self._lock:
            self._results[(principal_id, idempotency_key)] = result
