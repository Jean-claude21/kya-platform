"""Register governed Data Foundation capabilities on the KYA MCP gateway."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypeVar
from uuid import UUID, uuid7

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from kya_platform.application.data import CommandMetadata, IngestionRunReport, SnapshotLineage
from kya_platform.application.reliability import canonical_request_hash
from kya_platform.domain.data import (
    DataAsset,
    DataContract,
    DataPipeline,
    DataSnapshot,
    IngestionRun,
    RunStatus,
)
from kya_platform.mcp.data.contracts import (
    DataAssetDetail,
    DataAssetSummary,
    DataContractDetail,
    DataDiscoveryResult,
    IngestionAccepted,
    IngestionRunDetail,
    LineageResult,
    QualityResultDetail,
    SnapshotListResult,
    SnapshotSummary,
)
from kya_platform.mcp.registry.contracts import Confirmation
from kya_platform.mcp.registry.server import RegistryGuard

T = TypeVar("T")


class DataMcpBackend(Protocol):
    async def search_assets(
        self, unit_key: str, query: str, *, limit: int
    ) -> Sequence[DataAsset]: ...

    async def get_asset(self, unit_key: str, asset_key: str) -> DataAsset | None: ...

    async def get_contract(
        self, unit_key: str, asset_key: str, *, version: str | None = None
    ) -> DataContract | None: ...

    async def list_snapshots(
        self, unit_key: str, asset_key: str, *, limit: int
    ) -> Sequence[DataSnapshot]: ...

    async def trace_lineage(self, unit_key: str, snapshot_id: UUID) -> SnapshotLineage | None: ...

    async def get_pipeline(self, unit_key: str, pipeline_key: str) -> DataPipeline | None: ...

    async def get_run_report(self, unit_key: str, run_id: UUID) -> IngestionRunReport | None: ...

    async def start_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun: ...


class DataMcpAuditSink(Protocol):
    async def ensure_available(self) -> None: ...

    async def record(
        self,
        *,
        actor_id: UUID,
        active_unit: str,
        tool_name: str,
        target_type: str,
        target_id: str,
        decision: str,
        outcome: str,
        correlation_id: UUID,
    ) -> None: ...


class GovernedDataExecution:
    def __init__(self, guard: RegistryGuard, audit: DataMcpAuditSink) -> None:
        self._guard = guard
        self._audit = audit

    async def run(
        self,
        tool_name: str,
        *,
        target_type: str,
        target_id: str,
        operation: Callable[[str, UUID, UUID], Awaitable[T]],
    ) -> T:
        await self._audit.ensure_available()
        actor_id = self._guard.principal_id(tool_name)
        active_unit = self._guard.active_unit(tool_name)
        correlation_id = uuid7()
        try:
            await self._guard.require(tool_name, active_unit)
        except ToolError:
            await self._audit.record(
                actor_id=actor_id,
                active_unit=active_unit,
                tool_name=tool_name,
                target_type=target_type,
                target_id=target_id,
                decision="denied",
                outcome="rejected",
                correlation_id=correlation_id,
            )
            raise
        try:
            result = await operation(active_unit, actor_id, correlation_id)
        except Exception:
            await self._audit.record(
                actor_id=actor_id,
                active_unit=active_unit,
                tool_name=tool_name,
                target_type=target_type,
                target_id=target_id,
                decision="allowed",
                outcome="failed",
                correlation_id=correlation_id,
            )
            raise
        await self._audit.record(
            actor_id=actor_id,
            active_unit=active_unit,
            tool_name=tool_name,
            target_type=target_type,
            target_id=target_id,
            decision="allowed",
            outcome="succeeded",
            correlation_id=correlation_id,
        )
        return result


def register_data_tools(
    server: MCPServer[None],
    *,
    backend: DataMcpBackend,
    guard: RegistryGuard,
    audit: DataMcpAuditSink,
) -> None:
    """Add a bounded Data toolset; storage references and secrets stay server-side."""

    execution = GovernedDataExecution(guard, audit)

    @server.tool(name="discover_data_assets", structured_output=True)
    async def discover_data_assets(query: str, limit: int = 20) -> DataDiscoveryResult:
        """Trouver les actifs visibles dans l'unité KYA active."""
        if not 2 <= len(query.strip()) <= 200:
            raise ToolError("query_length_invalid")
        if not 1 <= limit <= 50:
            raise ToolError("limit_invalid")

        async def search(unit: str, actor: UUID, correlation: UUID) -> DataDiscoveryResult:
            del actor
            items = await backend.search_assets(unit, query, limit=limit + 1)
            return DataDiscoveryResult(
                items=tuple(DataAssetSummary.from_domain(item) for item in items[:limit]),
                active_unit=unit,
                has_more=len(items) > limit,
                correlation_id=correlation,
            )

        return await execution.run(
            "discover_data_assets",
            target_type="data_catalog",
            target_id="active-unit",
            operation=search,
        )

    @server.tool(name="get_data_asset", structured_output=True)
    async def get_data_asset(asset_key: str) -> DataAssetDetail:
        """Lire les métadonnées gouvernées d'un actif, jamais ses secrets."""

        async def get(unit: str, actor: UUID, correlation: UUID) -> DataAssetDetail:
            del actor
            asset = await backend.get_asset(unit, asset_key)
            if asset is None:
                raise ToolError("data_asset_not_found")
            return DataAssetDetail.from_detail(asset, active_unit=unit, correlation_id=correlation)

        return await execution.run(
            "get_data_asset",
            target_type="data_asset",
            target_id=asset_key,
            operation=get,
        )

    @server.tool(name="get_data_contract", structured_output=True)
    async def get_data_contract(asset_key: str, version: str | None = None) -> DataContractDetail:
        """Lire le schéma, la qualité, la fraîcheur et la rétention applicables."""

        async def get(unit: str, actor: UUID, correlation: UUID) -> DataContractDetail:
            del actor
            contract = await backend.get_contract(unit, asset_key, version=version)
            if contract is None:
                raise ToolError("data_contract_not_found")
            return DataContractDetail.from_domain(
                contract,
                asset_key=asset_key,
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "get_data_contract",
            target_type="data_asset",
            target_id=asset_key,
            operation=get,
        )

    @server.tool(name="list_data_snapshots", structured_output=True)
    async def list_data_snapshots(asset_key: str, limit: int = 20) -> SnapshotListResult:
        """Lister des preuves de données sans exposer les emplacements de stockage."""
        if not 1 <= limit <= 50:
            raise ToolError("limit_invalid")

        async def listing(unit: str, actor: UUID, correlation: UUID) -> SnapshotListResult:
            del actor
            asset = await backend.get_asset(unit, asset_key)
            if asset is None:
                raise ToolError("data_asset_not_found")
            items = await backend.list_snapshots(unit, asset_key, limit=limit + 1)
            return SnapshotListResult(
                asset_key=asset_key,
                items=tuple(SnapshotSummary.from_domain(item) for item in items[:limit]),
                active_unit=unit,
                has_more=len(items) > limit,
                correlation_id=correlation,
            )

        return await execution.run(
            "list_data_snapshots",
            target_type="data_asset",
            target_id=asset_key,
            operation=listing,
        )

    @server.tool(name="trace_data_lineage", structured_output=True)
    async def trace_data_lineage(snapshot_id: UUID) -> LineageResult:
        """Expliquer les dépendances exactes d'un snapshot visible."""

        async def trace(unit: str, actor: UUID, correlation: UUID) -> LineageResult:
            del actor
            lineage = await backend.trace_lineage(unit, snapshot_id)
            if lineage is None:
                raise ToolError("data_snapshot_not_found")
            return LineageResult(
                snapshot_id=lineage.snapshot_id,
                input_snapshot_ids=lineage.input_snapshot_ids,
                output_snapshot_ids=lineage.output_snapshot_ids,
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "trace_data_lineage",
            target_type="data_snapshot",
            target_id=str(snapshot_id),
            operation=trace,
        )

    @server.tool(name="start_ingestion", structured_output=True)
    async def start_ingestion(
        pipeline_key: str,
        idempotency_key: str,
        confirmation: Confirmation,
    ) -> IngestionAccepted:
        """Créer une exécution durable ; le connecteur déterministe la traitera ensuite."""
        del confirmation
        if not 16 <= len(idempotency_key) <= 200:
            raise ToolError("idempotency_key_invalid")

        async def start(unit: str, actor: UUID, correlation: UUID) -> IngestionAccepted:
            pipeline = await backend.get_pipeline(unit, pipeline_key)
            if pipeline is None:
                raise ToolError("data_pipeline_not_found")
            started_at = datetime.now(UTC)
            run = IngestionRun(uuid7(), pipeline.id, actor, RunStatus.STARTED, started_at)
            request_hash = canonical_request_hash(
                {
                    "pipeline_key": pipeline_key,
                    "active_unit": unit,
                    "confirmed": True,
                }
            )
            persisted = await backend.start_run(
                unit,
                run,
                command=CommandMetadata(
                    actor_id=actor,
                    correlation_id=correlation,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    expires_at=started_at + timedelta(hours=24),
                ),
            )
            return IngestionAccepted(
                run_id=persisted.id,
                pipeline_key=pipeline_key,
                status=persisted.status.value,
                started_at=persisted.started_at,
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "start_ingestion",
            target_type="data_pipeline",
            target_id=pipeline_key,
            operation=start,
        )

    @server.tool(name="get_ingestion_run", structured_output=True)
    async def get_ingestion_run(run_id: UUID) -> IngestionRunDetail:
        """Suivre une collecte et ses contrôles qualité sans exposer le stockage."""

        async def get(unit: str, actor: UUID, correlation: UUID) -> IngestionRunDetail:
            del actor
            report = await backend.get_run_report(unit, run_id)
            if report is None:
                raise ToolError("data_ingestion_run_not_found")
            return IngestionRunDetail(
                run_id=report.run.id,
                pipeline_key=report.pipeline_key,
                status=report.run.status.value,
                started_at=report.run.started_at,
                completed_at=report.run.completed_at,
                error_code=report.run.error_code,
                snapshot=(
                    SnapshotSummary.from_domain(report.snapshot)
                    if report.snapshot is not None
                    else None
                ),
                quality_results=tuple(
                    QualityResultDetail.from_domain(result) for result in report.quality_results
                ),
                active_unit=unit,
                correlation_id=correlation,
            )

        return await execution.run(
            "get_ingestion_run",
            target_type="data_run",
            target_id=str(run_id),
            operation=get,
        )


__all__ = ["DataMcpAuditSink", "DataMcpBackend", "register_data_tools"]
