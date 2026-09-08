"""Register KYA Intelligence tools on the governed MCP gateway."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid7

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import (
    IntelligenceConflictError,
    IntelligenceReferenceError,
    IntelligenceStateError,
)
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch, WatchEvaluation
from kya_platform.mcp.data.server import DataMcpAuditSink, GovernedDataExecution
from kya_platform.mcp.intelligence.contracts import (
    SignalDetail,
    SignalListResult,
    WatchDefinitionInput,
    WatchDetail,
    WatchEvaluationResult,
    WatchListResult,
)
from kya_platform.mcp.registry.contracts import Confirmation
from kya_platform.mcp.registry.server import RegistryGuard


class IntelligenceMcpBackend(Protocol):
    async def resolve_unit_id(self, unit_key: str) -> UUID | None: ...
    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch: ...
    async def list_watches(self, unit_key: str, *, limit: int) -> Sequence[IntelligenceWatch]: ...
    async def evaluate_watch(
        self, unit_key: str, watch_key: str, *, limit: int, command: CommandMetadata
    ) -> WatchEvaluation: ...
    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool, limit: int
    ) -> Sequence[IntelligenceSignal]: ...
    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal: ...


def register_intelligence_tools(
    server: MCPServer[None],
    *,
    backend: IntelligenceMcpBackend,
    guard: RegistryGuard,
    audit: DataMcpAuditSink,
) -> None:
    execution = GovernedDataExecution(guard, audit)

    def command(actor: UUID, correlation: UUID, key: str, body: object) -> CommandMetadata:
        return CommandMetadata(
            actor,
            correlation,
            key,
            canonical_request_hash(cast(JsonValue, body)),
            datetime.now(UTC) + timedelta(hours=24),
        )

    @server.tool(name="list_intelligence_watches", structured_output=True)
    async def list_watches(limit: int = 20) -> WatchListResult:
        if not 1 <= limit <= 100:
            raise ToolError("limit_invalid")

        async def listing(unit: str, actor: UUID, correlation: UUID) -> WatchListResult:
            del actor
            items = await backend.list_watches(unit, limit=limit)
            return WatchListResult(
                items=tuple(WatchDetail.from_domain(item) for item in items),
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "list_intelligence_watches",
            target_type="intelligence_watch",
            target_id="active-unit",
            operation=listing,
        )

    @server.tool(name="create_intelligence_watch", structured_output=True)
    async def create_watch(
        definition: WatchDefinitionInput, idempotency_key: str, confirmation: Confirmation
    ) -> WatchDetail:
        del confirmation
        if not 16 <= len(idempotency_key) <= 200:
            raise ToolError("idempotency_key_invalid")

        async def creating(unit: str, actor: UUID, correlation: UUID) -> WatchDetail:
            unit_id = await backend.resolve_unit_id(unit)
            if unit_id is None:
                raise ToolError("organizational_unit_not_found")
            try:
                item = await backend.create_watch(
                    unit,
                    IntelligenceWatch(
                        uuid7(),
                        definition.key,
                        definition.name,
                        definition.query,
                        unit_id,
                        actor,
                        definition.asset_keys,
                    ),
                    command=command(
                        actor, correlation, idempotency_key, definition.model_dump(mode="json")
                    ),
                )
            except (IntelligenceConflictError, IntelligenceReferenceError) as error:
                raise ToolError(str(error)) from error
            return WatchDetail.from_domain(item)

        return await execution.run(
            "create_intelligence_watch",
            target_type="intelligence_watch",
            target_id=definition.key,
            operation=creating,
        )

    @server.tool(name="evaluate_intelligence_watch", structured_output=True)
    async def evaluate_watch(
        watch_key: str, idempotency_key: str, confirmation: Confirmation, limit: int = 50
    ) -> WatchEvaluationResult:
        del confirmation
        if not 1 <= limit <= 50 or not 16 <= len(idempotency_key) <= 200:
            raise ToolError("request_invalid")

        async def evaluating(unit: str, actor: UUID, correlation: UUID) -> WatchEvaluationResult:
            try:
                result = await backend.evaluate_watch(
                    unit,
                    watch_key,
                    limit=limit,
                    command=command(
                        actor,
                        correlation,
                        idempotency_key,
                        {"watch_key": watch_key, "limit": limit},
                    ),
                )
            except (
                IntelligenceConflictError,
                IntelligenceReferenceError,
                IntelligenceStateError,
            ) as error:
                raise ToolError(str(error)) from error
            return WatchEvaluationResult(
                watch=WatchDetail.from_domain(result.watch),
                matched_count=result.matched_count,
                created_count=len(result.created_signals),
                created_signals=tuple(
                    SignalDetail.from_domain(item) for item in result.created_signals
                ),
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "evaluate_intelligence_watch",
            target_type="intelligence_watch",
            target_id=watch_key,
            operation=evaluating,
        )

    @server.tool(name="list_intelligence_signals", structured_output=True)
    async def list_signals(
        watch_key: str, only_open: bool = True, limit: int = 20
    ) -> SignalListResult:
        if not 1 <= limit <= 100:
            raise ToolError("limit_invalid")

        async def listing(unit: str, actor: UUID, correlation: UUID) -> SignalListResult:
            del actor
            items = await backend.list_signals(
                unit, watch_key, only_open=only_open, limit=limit + 1
            )
            return SignalListResult(
                watch_key=watch_key,
                items=tuple(SignalDetail.from_domain(item) for item in items[:limit]),
                active_unit=unit,
                has_more=len(items) > limit,
                correlation_id=correlation,
            )

        return await execution.run(
            "list_intelligence_signals",
            target_type="intelligence_watch",
            target_id=watch_key,
            operation=listing,
        )

    @server.tool(name="acknowledge_intelligence_signal", structured_output=True)
    async def acknowledge_signal(
        signal_id: UUID, expected_revision: int, idempotency_key: str, confirmation: Confirmation
    ) -> SignalDetail:
        del confirmation
        if expected_revision < 1 or not 16 <= len(idempotency_key) <= 200:
            raise ToolError("request_invalid")

        async def acknowledging(unit: str, actor: UUID, correlation: UUID) -> SignalDetail:
            try:
                item = await backend.acknowledge_signal(
                    unit,
                    signal_id,
                    expected_revision=expected_revision,
                    acknowledged_at=datetime.now(UTC),
                    command=command(
                        actor,
                        correlation,
                        idempotency_key,
                        {"signal_id": str(signal_id), "expected_revision": expected_revision},
                    ),
                )
            except (
                IntelligenceConflictError,
                IntelligenceReferenceError,
                IntelligenceStateError,
            ) as error:
                raise ToolError(str(error)) from error
            return SignalDetail.from_domain(item)

        return await execution.run(
            "acknowledge_intelligence_signal",
            target_type="intelligence_signal",
            target_id=str(signal_id),
            operation=acknowledging,
        )


__all__ = ["IntelligenceMcpBackend", "register_intelligence_tools"]
