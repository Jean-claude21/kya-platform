"""Transactional PostgreSQL adapter for autonomous source flows."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.data import CommandMetadata
from kya_platform.application.source_lifecycle import (
    SourceFlowConflictError,
    SourceFlowReferenceError,
    SourceFlowStateError,
)
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSource,
    DataSourceKind,
    DataStatus,
    IngestionRun,
    QualityRule,
    RunStatus,
)
from kya_platform.domain.source_lifecycle import (
    IngestionSchedule,
    SourceFlow,
    SourceFlowDraft,
    SourceFlowHealth,
)
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    CatalogArtifact,
    CatalogArtifactVersion,
    CoreOrganizationalUnit,
    DataAssetRow,
    DataContractVersionRow,
    DataIngestionRunRow,
    DataIngestionScheduleRow,
    DataPipelineRow,
    DataQualityResultRow,
    DataSnapshotRow,
    DataSourceFlowRow,
    DataSourceRow,
    IdempotencyRecord,
    OutboxEvent,
)

SYSTEM_ACTOR = UUID(int=0)


def _source(row: DataSourceRow) -> DataSource:
    return DataSource(
        row.id,
        row.key,
        row.name,
        DataSourceKind(row.kind),
        row.owner_unit_id,
        row.system_artifact_id,
        row.secret_reference,
        DataStatus(row.status),
        cast(dict[str, object], row.configuration or {}),
    )


def _asset(row: DataAssetRow) -> DataAsset:
    return DataAsset(
        row.id,
        row.key,
        row.name,
        row.owner_unit_id,
        DataAssetLayer(row.layer),
        DataClassification(row.classification),
        DataStatus(row.status),
    )


def _contract(row: DataContractVersionRow) -> DataContract:
    return DataContract(
        row.id,
        row.asset_id,
        row.version,
        cast(dict[str, object], row.schema_document),
        row.digest,
        tuple(
            QualityRule(
                cast(str, item["key"]),
                cast(str, item["kind"]),
                cast(str, item["expression"]),
                cast(str, item.get("severity", "error")),
            )
            for item in row.quality_rules
        ),
        row.freshness_minutes,
        row.retention_days,
    )


def _pipeline(row: DataPipelineRow) -> DataPipeline:
    return DataPipeline(
        row.id,
        row.key,
        row.name,
        row.owner_unit_id,
        row.source_id,
        row.connector_version_id,
        row.output_asset_id,
        DataStatus(row.status),
    )


def _schedule(row: DataIngestionScheduleRow | None) -> IngestionSchedule | None:
    if row is None:
        return None
    return IngestionSchedule(
        row.id,
        row.pipeline_id,
        row.interval_minutes,
        row.next_run_at,
        row.enabled,
        row.revision,
        row.last_claimed_at,
    )


def _run(row: DataIngestionRunRow) -> IngestionRun:
    return IngestionRun(
        row.id,
        row.pipeline_id,
        row.triggered_by,
        RunStatus(row.status),
        row.started_at,
        row.completed_at,
        row.error_code,
    )


class SqlAlchemySourceLifecycleRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def configure(
        self,
        unit_key: str,
        draft: SourceFlowDraft,
        *,
        schedule: IngestionSchedule | None,
        command: CommandMetadata,
    ) -> SourceFlow:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                scope = f"data:flow:configure:{unit_id}:{command.actor_id}"
                replay = await self._replay_pipeline_id(session, scope, command)
                if replay is not None:
                    flow = await self._load_by_pipeline(session, unit_id, replay)
                    if flow is None:
                        raise SourceFlowReferenceError("idempotent source flow is unavailable")
                    return flow
                if draft.source.owner_unit_id != unit_id:
                    raise SourceFlowReferenceError("source flow owner does not match unit")
                connector = (
                    await session.execute(
                        select(CatalogArtifactVersion, CatalogArtifact)
                        .join(
                            CatalogArtifact,
                            CatalogArtifact.id == CatalogArtifactVersion.artifact_id,
                        )
                        .where(
                            CatalogArtifact.slug == draft.connector_key,
                            CatalogArtifact.artifact_type == "connector",
                            CatalogArtifactVersion.version == draft.connector_version,
                            CatalogArtifactVersion.status == "published",
                        )
                    )
                ).first()
                if connector is None:
                    raise SourceFlowReferenceError("published connector version does not exist")
                connector_version = connector[0]
                source = draft.source
                asset = draft.asset
                pipeline = DataPipeline(
                    draft.pipeline.id,
                    draft.pipeline.key,
                    draft.pipeline.name,
                    draft.pipeline.owner_unit_id,
                    draft.pipeline.source_id,
                    connector_version.id,
                    draft.pipeline.output_asset_id,
                    draft.pipeline.status,
                )
                session.add_all(
                    [
                        DataSourceRow(
                            id=source.id,
                            key=source.key,
                            name=source.name,
                            kind=source.kind.value,
                            owner_unit_id=unit_id,
                            system_artifact_id=connector[1].id,
                            secret_reference=source.secret_reference,
                            configuration=source.configuration,
                            status=source.status.value,
                            created_by=command.actor_id,
                        ),
                        DataAssetRow(
                            id=asset.id,
                            key=asset.key,
                            name=asset.name,
                            owner_unit_id=unit_id,
                            layer=asset.layer.value,
                            classification=asset.classification.value,
                            status=asset.status.value,
                            created_by=command.actor_id,
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        DataContractVersionRow(
                            id=draft.contract.id,
                            asset_id=asset.id,
                            version=draft.contract.version,
                            schema_document=draft.contract.schema,
                            quality_rules=[
                                {
                                    "key": rule.key,
                                    "kind": rule.kind,
                                    "expression": rule.expression,
                                    "severity": rule.severity,
                                }
                                for rule in draft.contract.quality_rules
                            ],
                            freshness_minutes=draft.contract.freshness_minutes,
                            retention_days=draft.contract.retention_days,
                            digest=draft.contract.digest,
                            created_by=command.actor_id,
                        ),
                        DataPipelineRow(
                            id=pipeline.id,
                            key=pipeline.key,
                            name=pipeline.name,
                            owner_unit_id=unit_id,
                            source_id=source.id,
                            connector_version_id=connector_version.id,
                            output_asset_id=asset.id,
                            status=pipeline.status.value,
                            created_by=command.actor_id,
                        ),
                    ]
                )
                await session.flush()
                session.add(
                    DataSourceFlowRow(
                        pipeline_id=pipeline.id, revision=1, updated_by=command.actor_id
                    )
                )
                if schedule is not None:
                    session.add(
                        DataIngestionScheduleRow(
                            id=schedule.id,
                            pipeline_id=pipeline.id,
                            interval_minutes=schedule.interval_minutes,
                            next_run_at=schedule.next_run_at,
                            enabled=schedule.enabled,
                            revision=1,
                            created_by=command.actor_id,
                            updated_by=command.actor_id,
                        )
                    )
                session.add(
                    self._event("kya.data.source-flow.configured.v1", pipeline, unit_id, command)
                )
                session.add(
                    self._audit("data.source-flow.configure", pipeline, unit_id, command, 1)
                )
                self._remember(session, scope, command, pipeline.id)
                return SourceFlow(
                    pipeline.key,
                    source,
                    asset,
                    draft.contract,
                    pipeline,
                    1,
                    IngestionSchedule(
                        schedule.id,
                        pipeline.id,
                        schedule.interval_minutes,
                        schedule.next_run_at,
                        schedule.enabled,
                    )
                    if schedule is not None
                    else None,
                )
        except IntegrityError as error:
            raise SourceFlowConflictError("source flow keys or version already exist") from error

    async def get(self, unit_key: str, flow_key: str) -> SourceFlow | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            return await self._load_by_key(session, unit_id, flow_key)

    async def get_health(self, unit_key: str, flow_key: str) -> SourceFlowHealth | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            flow = await self._load_by_key(session, unit_id, flow_key)
            if flow is None:
                return None
            latest_run = await session.scalar(
                select(DataIngestionRunRow)
                .where(DataIngestionRunRow.pipeline_id == flow.pipeline.id)
                .order_by(DataIngestionRunRow.started_at.desc(), DataIngestionRunRow.id.desc())
                .limit(1)
            )
            if latest_run is None:
                return SourceFlowHealth(flow)
            snapshot = await session.scalar(
                select(DataSnapshotRow).where(DataSnapshotRow.run_id == latest_run.id).limit(1)
            )
            quality_status: str | None = None
            if snapshot is not None:
                statuses = tuple(
                    await session.scalars(
                        select(DataQualityResultRow.status).where(
                            DataQualityResultRow.snapshot_id == snapshot.id
                        )
                    )
                )
                quality_status = (
                    "failed"
                    if "failed" in statuses
                    else "warning"
                    if "warning" in statuses
                    else "passed"
                    if statuses
                    else None
                )
            return SourceFlowHealth(
                flow,
                _run(latest_run),
                snapshot.id if snapshot is not None else None,
                snapshot.observed_at if snapshot is not None else None,
                quality_status,
            )

    async def transition(
        self,
        unit_key: str,
        flow_key: str,
        status: DataStatus,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        async with self._sessions() as session, session.begin():
            unit_id = await self._required_unit_id(session, unit_key)
            pipeline = await session.scalar(
                select(DataPipelineRow)
                .where(DataPipelineRow.owner_unit_id == unit_id, DataPipelineRow.key == flow_key)
                .with_for_update()
            )
            if pipeline is None:
                raise SourceFlowReferenceError("source flow does not exist")
            control = await session.get(DataSourceFlowRow, pipeline.id, with_for_update=True)
            if control is None:
                raise SourceFlowReferenceError("source flow control is unavailable")
            scope = f"data:flow:{status.value}:{pipeline.id}:{command.actor_id}"
            replay = await self._replay_pipeline_id(session, scope, command)
            if replay is not None:
                flow = await self._load_by_pipeline(session, unit_id, replay)
                assert flow is not None
                return flow
            if control.revision != expected_revision:
                raise SourceFlowConflictError("source flow revision is stale")
            source = await session.get(DataSourceRow, pipeline.source_id)
            asset = await session.get(DataAssetRow, pipeline.output_asset_id)
            if source is None or asset is None:
                raise SourceFlowReferenceError("source flow components are unavailable")
            current_states = {source.status, asset.status, pipeline.status}
            allowed_sources = (
                {"draft", "active", "paused"}
                if status is DataStatus.ACTIVE
                else {"active", "paused"}
            )
            if len(current_states) != 1 or not current_states <= allowed_sources:
                raise SourceFlowStateError("source flow cannot transition from its current state")
            source.status = asset.status = pipeline.status = status.value
            control.revision += 1
            control.updated_by = command.actor_id
            session.add(
                self._event(
                    f"kya.data.source-flow.{status.value}.v1", _pipeline(pipeline), unit_id, command
                )
            )
            session.add(
                self._audit(
                    f"data.source-flow.{status.value}",
                    _pipeline(pipeline),
                    unit_id,
                    command,
                    control.revision,
                )
            )
            self._remember(session, scope, command, pipeline.id)
        flow = await self.get(unit_key, flow_key)
        assert flow is not None
        return flow

    async def put_schedule(
        self,
        unit_key: str,
        flow_key: str,
        schedule: IngestionSchedule,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        async with self._sessions() as session, session.begin():
            unit_id = await self._required_unit_id(session, unit_key)
            pipeline = await session.scalar(
                select(DataPipelineRow)
                .where(DataPipelineRow.owner_unit_id == unit_id, DataPipelineRow.key == flow_key)
                .with_for_update()
            )
            if pipeline is None:
                raise SourceFlowReferenceError("source flow does not exist")
            control = await session.get(DataSourceFlowRow, pipeline.id, with_for_update=True)
            if control is None:
                raise SourceFlowReferenceError("source flow control is unavailable")
            scope = f"data:flow:schedule:{pipeline.id}:{command.actor_id}"
            replay = await self._replay_pipeline_id(session, scope, command)
            if replay is not None:
                flow = await self._load_by_pipeline(session, unit_id, replay)
                assert flow is not None
                return flow
            if control.revision != expected_revision:
                raise SourceFlowConflictError("source flow revision is stale")
            existing = await session.scalar(
                select(DataIngestionScheduleRow)
                .where(DataIngestionScheduleRow.pipeline_id == pipeline.id)
                .with_for_update()
            )
            if existing is None:
                session.add(
                    DataIngestionScheduleRow(
                        id=schedule.id,
                        pipeline_id=pipeline.id,
                        interval_minutes=schedule.interval_minutes,
                        next_run_at=schedule.next_run_at,
                        enabled=schedule.enabled,
                        revision=1,
                        created_by=command.actor_id,
                        updated_by=command.actor_id,
                    )
                )
            else:
                existing.interval_minutes = schedule.interval_minutes
                existing.next_run_at = schedule.next_run_at
                existing.enabled = schedule.enabled
                existing.revision += 1
                existing.updated_by = command.actor_id
            control.revision += 1
            control.updated_by = command.actor_id
            session.add(
                self._event(
                    "kya.data.source-flow.scheduled.v1", _pipeline(pipeline), unit_id, command
                )
            )
            session.add(
                self._audit(
                    "data.source-flow.schedule",
                    _pipeline(pipeline),
                    unit_id,
                    command,
                    control.revision,
                )
            )
            self._remember(session, scope, command, pipeline.id)
        flow = await self.get(unit_key, flow_key)
        assert flow is not None
        return flow

    async def claim_due_runs(self, *, now: datetime, limit: int) -> Sequence[IngestionRun]:
        runs: list[IngestionRun] = []
        async with self._sessions() as session, session.begin():
            schedules = tuple(
                await session.scalars(
                    select(DataIngestionScheduleRow)
                    .join(
                        DataPipelineRow, DataPipelineRow.id == DataIngestionScheduleRow.pipeline_id
                    )
                    .join(DataSourceRow, DataSourceRow.id == DataPipelineRow.source_id)
                    .join(DataAssetRow, DataAssetRow.id == DataPipelineRow.output_asset_id)
                    .where(
                        DataIngestionScheduleRow.enabled.is_(True),
                        DataIngestionScheduleRow.next_run_at <= now,
                        DataPipelineRow.status == "active",
                        DataSourceRow.status == "active",
                        DataAssetRow.status == "active",
                    )
                    .order_by(DataIngestionScheduleRow.next_run_at, DataIngestionScheduleRow.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for schedule in schedules:
                pipeline = await session.get(DataPipelineRow, schedule.pipeline_id)
                assert pipeline is not None
                source = await session.get(DataSourceRow, pipeline.source_id)
                assert source is not None
                contract = await session.scalar(
                    select(DataContractVersionRow)
                    .where(DataContractVersionRow.asset_id == pipeline.output_asset_id)
                    .order_by(
                        DataContractVersionRow.created_at.desc(), DataContractVersionRow.id.desc()
                    )
                    .limit(1)
                )
                if contract is None:
                    continue
                due_at = schedule.next_run_at
                next_run_at = due_at + timedelta(minutes=schedule.interval_minutes)
                while next_run_at <= now:
                    next_run_at += timedelta(minutes=schedule.interval_minutes)
                schedule.last_claimed_at = due_at
                schedule.next_run_at = next_run_at
                schedule.revision += 1
                run = IngestionRun(uuid7(), pipeline.id, SYSTEM_ACTOR, RunStatus.STARTED, now)
                correlation_id = uuid7()
                event = OutboxEvent(
                    topic="kya.data.run.started.v1",
                    aggregate_type="data_run",
                    aggregate_id=str(run.id),
                    correlation_id=correlation_id,
                    payload={
                        "schema_version": "1",
                        "aggregate_id": str(run.id),
                        "scope_unit_id": str(pipeline.owner_unit_id),
                        "actor_id": str(SYSTEM_ACTOR),
                        "correlation_id": str(correlation_id),
                        "unit_key": await self._unit_key(session, pipeline.owner_unit_id),
                        "pipeline_id": str(pipeline.id),
                        "pipeline_key": pipeline.key,
                        "source_id": str(source.id),
                        "source_configuration": source.configuration,
                        "asset_id": str(pipeline.output_asset_id),
                        "contract_id": str(contract.id),
                        "schedule_id": str(schedule.id),
                        "scheduled_for": due_at.isoformat(),
                    },
                )
                session.add_all(
                    [
                        DataIngestionRunRow(
                            id=run.id,
                            pipeline_id=run.pipeline_id,
                            triggered_by=run.triggered_by,
                            status=run.status.value,
                            started_at=run.started_at,
                            metrics={"trigger": "schedule", "scheduled_for": due_at.isoformat()},
                        ),
                        event,
                    ]
                )
                runs.append(run)
        return tuple(runs)

    async def _load_by_key(
        self, session: AsyncSession, unit_id: UUID, key: str
    ) -> SourceFlow | None:
        pipeline = await session.scalar(
            select(DataPipelineRow).where(
                DataPipelineRow.owner_unit_id == unit_id, DataPipelineRow.key == key
            )
        )
        if pipeline is None:
            return None
        return await self._load_by_pipeline(session, unit_id, pipeline.id)

    async def _load_by_pipeline(
        self, session: AsyncSession, unit_id: UUID, pipeline_id: UUID
    ) -> SourceFlow | None:
        pipeline = await session.get(DataPipelineRow, pipeline_id)
        if pipeline is None or pipeline.owner_unit_id != unit_id:
            return None
        control = await session.get(DataSourceFlowRow, pipeline.id)
        source = await session.get(DataSourceRow, pipeline.source_id)
        asset = await session.get(DataAssetRow, pipeline.output_asset_id)
        contract = await session.scalar(
            select(DataContractVersionRow)
            .where(DataContractVersionRow.asset_id == pipeline.output_asset_id)
            .order_by(DataContractVersionRow.created_at.desc(), DataContractVersionRow.id.desc())
            .limit(1)
        )
        schedule = await session.scalar(
            select(DataIngestionScheduleRow).where(
                DataIngestionScheduleRow.pipeline_id == pipeline.id
            )
        )
        if control is None or source is None or asset is None or contract is None:
            return None
        return SourceFlow(
            pipeline.key,
            _source(source),
            _asset(asset),
            _contract(contract),
            _pipeline(pipeline),
            control.revision,
            _schedule(schedule),
        )

    @staticmethod
    async def _unit_id(session: AsyncSession, key: str) -> UUID | None:
        return cast(
            UUID | None,
            await session.scalar(
                select(CoreOrganizationalUnit.id).where(CoreOrganizationalUnit.key == key)
            ),
        )

    @classmethod
    async def _required_unit_id(cls, session: AsyncSession, key: str) -> UUID:
        unit_id = await cls._unit_id(session, key)
        if unit_id is None:
            raise SourceFlowReferenceError("organizational unit does not exist")
        return unit_id

    @staticmethod
    async def _unit_key(session: AsyncSession, unit_id: UUID) -> str:
        value = await session.scalar(
            select(CoreOrganizationalUnit.key).where(CoreOrganizationalUnit.id == unit_id)
        )
        if value is None:
            raise SourceFlowReferenceError("organizational unit does not exist")
        return value

    @staticmethod
    async def _replay_pipeline_id(
        session: AsyncSession, scope: str, command: CommandMetadata
    ) -> UUID | None:
        record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == command.idempotency_key,
            )
        )
        if record is None:
            return None
        if record.request_hash != command.request_hash:
            raise SourceFlowConflictError("idempotency key belongs to another request")
        value = record.response_body.get("pipeline_id")
        if not isinstance(value, str):
            raise SourceFlowConflictError("idempotency evidence is invalid")
        return UUID(value)

    @staticmethod
    def _remember(
        session: AsyncSession,
        scope: str,
        command: CommandMetadata,
        pipeline_id: UUID,
    ) -> None:
        session.add(
            IdempotencyRecord(
                scope=scope,
                idempotency_key=command.idempotency_key,
                request_hash=command.request_hash,
                response_status=200,
                response_body={"pipeline_id": str(pipeline_id)},
                expires_at=command.expires_at,
            )
        )

    @staticmethod
    def _event(
        topic: str,
        pipeline: DataPipeline,
        unit_id: UUID,
        command: CommandMetadata,
    ) -> OutboxEvent:
        return OutboxEvent(
            topic=topic,
            aggregate_type="source_flow",
            aggregate_id=str(pipeline.id),
            correlation_id=command.correlation_id,
            payload={
                "schema_version": "1",
                "aggregate_id": str(pipeline.id),
                "flow_key": pipeline.key,
                "scope_unit_id": str(unit_id),
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
            },
        )

    @staticmethod
    def _audit(
        action: str,
        pipeline: DataPipeline,
        unit_id: UUID,
        command: CommandMetadata,
        revision: int,
    ) -> AuditEvent:
        return AuditEvent(
            actor_id=command.actor_id,
            action=action,
            target_type="source_flow",
            target_id=str(pipeline.id),
            scope=f"org_unit:{unit_id}",
            decision="allowed",
            outcome="succeeded",
            correlation_id=command.correlation_id,
            event_metadata={"flow_key": pipeline.key, "revision": revision},
        )


__all__ = ["SqlAlchemySourceLifecycleRepository"]
