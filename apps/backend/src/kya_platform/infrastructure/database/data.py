"""Transactional Neon adapter for KYA Data Foundation."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.data import (
    CommandMetadata,
    DataConflictError,
    DataReferenceError,
    DataStateError,
    IngestionRunReport,
    RunCompletion,
    SnapshotLineage,
)
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataSource,
    DataSourceKind,
    DataStatus,
    IngestionRun,
    QualityResult,
    QualityRule,
    QualityStatus,
    RunStatus,
    StorageObject,
)
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CoreOrganizationalUnit,
    DataAssetRow,
    DataContentChunkRow,
    DataContentDocumentRow,
    DataContractVersionRow,
    DataIngestionRunRow,
    DataLineageEdgeRow,
    DataPipelineRow,
    DataQualityResultRow,
    DataSnapshotRow,
    DataSourceRow,
    IdempotencyRecord,
    OutboxEvent,
)


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
    rules = tuple(
        QualityRule(
            key=cast(str, rule["key"]),
            kind=cast(str, rule["kind"]),
            expression=cast(str, rule["expression"]),
            severity=cast(str, rule.get("severity", "error")),
        )
        for rule in row.quality_rules
    )
    return DataContract(
        row.id,
        row.asset_id,
        row.version,
        cast(dict[str, object], row.schema_document),
        row.digest,
        rules,
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


def _snapshot(row: DataSnapshotRow) -> DataSnapshot:
    return DataSnapshot(
        row.id,
        row.asset_id,
        row.run_id,
        row.contract_id,
        StorageObject(
            row.storage_provider,
            row.storage_container,
            row.object_key,
            row.object_version,
        ),
        row.content_digest,
        row.media_type,
        row.observed_at,
        row.row_count,
        row.byte_size,
    )


def _event(
    topic: str,
    aggregate_type: str,
    aggregate_id: UUID,
    scope_unit_id: UUID,
    command: CommandMetadata,
) -> OutboxEvent:
    return OutboxEvent(
        topic=topic,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        correlation_id=command.correlation_id,
        payload={
            "schema_version": "1",
            "aggregate_id": str(aggregate_id),
            "scope_unit_id": str(scope_unit_id),
            "actor_id": str(command.actor_id),
            "correlation_id": str(command.correlation_id),
        },
    )


class SqlAlchemyDataRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_sources(self, unit_key: str, *, limit: int) -> Sequence[DataSource]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            rows = await session.scalars(
                select(DataSourceRow)
                .where(DataSourceRow.owner_unit_id == unit_id)
                .order_by(DataSourceRow.name, DataSourceRow.id)
                .limit(limit)
            )
            return tuple(_source(row) for row in rows)

    async def create_source(
        self, unit_key: str, source: DataSource, *, command: CommandMetadata
    ) -> DataSource:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                replay = await self._replay_id(
                    session, f"data:source:create:{unit_id}:{command.actor_id}", command
                )
                if replay is not None:
                    row = await session.get(DataSourceRow, replay)
                    if row is None:
                        raise DataReferenceError("idempotent source is no longer available")
                    return _source(row)
                if source.owner_unit_id != unit_id:
                    raise DataReferenceError("source owner does not match the authorized scope")
                if source.system_artifact_id is not None:
                    if await session.get(CatalogArtifact, source.system_artifact_id) is None:
                        raise DataReferenceError("source system artifact does not exist")
                session.add_all(
                    [
                        DataSourceRow(
                            id=source.id,
                            key=source.key,
                            name=source.name,
                            kind=source.kind.value,
                            owner_unit_id=unit_id,
                            system_artifact_id=source.system_artifact_id,
                            secret_reference=source.secret_reference,
                            configuration=source.configuration,
                            status=source.status.value,
                            created_by=command.actor_id,
                        ),
                        _event(
                            "kya.data.source.created.v1",
                            "data_source",
                            source.id,
                            unit_id,
                            command,
                        ),
                    ]
                )
                self._remember(
                    session,
                    f"data:source:create:{unit_id}:{command.actor_id}",
                    command,
                    source.id,
                )
        except IntegrityError as error:
            raise DataConflictError("data source key already exists") from error
        return source

    async def list_assets(self, unit_key: str, *, limit: int) -> Sequence[DataAsset]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            rows = await session.scalars(
                select(DataAssetRow)
                .where(DataAssetRow.owner_unit_id == unit_id)
                .order_by(DataAssetRow.name, DataAssetRow.id)
                .limit(limit)
            )
            return tuple(_asset(row) for row in rows)

    async def search_assets(self, unit_key: str, query: str, *, limit: int) -> Sequence[DataAsset]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            normalized = query.strip().casefold()
            if not normalized:
                return ()
            rows = await session.scalars(
                select(DataAssetRow)
                .where(
                    DataAssetRow.owner_unit_id == unit_id,
                    or_(
                        func.lower(DataAssetRow.key).contains(normalized, autoescape=True),
                        func.lower(DataAssetRow.name).contains(normalized, autoescape=True),
                    ),
                )
                .order_by(DataAssetRow.name, DataAssetRow.id)
                .limit(limit)
            )
            return tuple(_asset(row) for row in rows)

    async def get_asset(self, unit_key: str, asset_key: str) -> DataAsset | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            row = await session.scalar(
                select(DataAssetRow).where(
                    DataAssetRow.owner_unit_id == unit_id,
                    DataAssetRow.key == asset_key,
                )
            )
            return _asset(row) if row is not None else None

    async def create_asset(
        self, unit_key: str, asset: DataAsset, *, command: CommandMetadata
    ) -> DataAsset:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                scope = f"data:asset:create:{unit_id}:{command.actor_id}"
                replay = await self._replay_id(session, scope, command)
                if replay is not None:
                    row = await session.get(DataAssetRow, replay)
                    if row is None:
                        raise DataReferenceError("idempotent asset is no longer available")
                    return _asset(row)
                if asset.owner_unit_id != unit_id:
                    raise DataReferenceError("asset owner does not match the authorized scope")
                session.add_all(
                    [
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
                        _event(
                            "kya.data.asset.created.v1", "data_asset", asset.id, unit_id, command
                        ),
                    ]
                )
                self._remember(session, scope, command, asset.id)
        except IntegrityError as error:
            raise DataConflictError("data asset key already exists") from error
        return asset

    async def publish_contract(
        self, unit_key: str, contract: DataContract, *, command: CommandMetadata
    ) -> DataContract:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                asset = await session.get(DataAssetRow, contract.asset_id)
                if asset is None or asset.owner_unit_id != unit_id:
                    raise DataReferenceError("contract asset is outside the authorized scope")
                scope = f"data:contract:publish:{contract.asset_id}:{command.actor_id}"
                replay = await self._replay_id(session, scope, command)
                if replay is not None:
                    row = await session.get(DataContractVersionRow, replay)
                    if row is None:
                        raise DataReferenceError("idempotent contract is no longer available")
                    return _contract(row)
                rules = [
                    {
                        "key": rule.key,
                        "kind": rule.kind,
                        "expression": rule.expression,
                        "severity": rule.severity,
                    }
                    for rule in contract.quality_rules
                ]
                session.add_all(
                    [
                        DataContractVersionRow(
                            id=contract.id,
                            asset_id=contract.asset_id,
                            version=contract.version,
                            schema_document=contract.schema,
                            quality_rules=rules,
                            freshness_minutes=contract.freshness_minutes,
                            retention_days=contract.retention_days,
                            digest=contract.digest,
                            created_by=command.actor_id,
                        ),
                        _event(
                            "kya.data.contract.published.v1",
                            "data_contract",
                            contract.id,
                            unit_id,
                            command,
                        ),
                    ]
                )
                self._remember(session, scope, command, contract.id)
        except IntegrityError as error:
            raise DataConflictError("contract version or digest already exists") from error
        return contract

    async def create_pipeline(
        self, unit_key: str, pipeline: DataPipeline, *, command: CommandMetadata
    ) -> DataPipeline:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                source = await session.get(DataSourceRow, pipeline.source_id)
                asset = await session.get(DataAssetRow, pipeline.output_asset_id)
                connector = (
                    await session.execute(
                        select(CatalogArtifactVersion, CatalogArtifact)
                        .join(
                            CatalogArtifact,
                            CatalogArtifact.id == CatalogArtifactVersion.artifact_id,
                        )
                        .where(CatalogArtifactVersion.id == pipeline.connector_version_id)
                    )
                ).first()
                if source is None or source.owner_unit_id != unit_id:
                    raise DataReferenceError("pipeline source is outside the authorized scope")
                if asset is None or asset.owner_unit_id != unit_id:
                    raise DataReferenceError(
                        "pipeline output asset is outside the authorized scope"
                    )
                if (
                    connector is None
                    or connector[0].status != "published"
                    or connector[1].artifact_type != "connector"
                ):
                    raise DataReferenceError("pipeline requires a published connector version")
                scope = f"data:pipeline:create:{unit_id}:{command.actor_id}"
                replay = await self._replay_id(session, scope, command)
                if replay is not None:
                    row = await session.get(DataPipelineRow, replay)
                    if row is None:
                        raise DataReferenceError("idempotent pipeline is no longer available")
                    return _pipeline(row)
                if pipeline.owner_unit_id != unit_id:
                    raise DataReferenceError("pipeline owner does not match the authorized scope")
                session.add_all(
                    [
                        DataPipelineRow(
                            id=pipeline.id,
                            key=pipeline.key,
                            name=pipeline.name,
                            owner_unit_id=unit_id,
                            source_id=pipeline.source_id,
                            connector_version_id=pipeline.connector_version_id,
                            output_asset_id=pipeline.output_asset_id,
                            status=pipeline.status.value,
                            created_by=command.actor_id,
                        ),
                        _event(
                            "kya.data.pipeline.created.v1",
                            "data_pipeline",
                            pipeline.id,
                            unit_id,
                            command,
                        ),
                    ]
                )
                self._remember(session, scope, command, pipeline.id)
        except IntegrityError as error:
            raise DataConflictError("data pipeline key already exists") from error
        return pipeline

    async def get_contract(
        self, unit_key: str, asset_key: str, *, version: str | None = None
    ) -> DataContract | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            statement = (
                select(DataContractVersionRow)
                .join(DataAssetRow, DataAssetRow.id == DataContractVersionRow.asset_id)
                .where(
                    DataAssetRow.owner_unit_id == unit_id,
                    DataAssetRow.key == asset_key,
                )
            )
            if version is not None:
                statement = statement.where(DataContractVersionRow.version == version)
            else:
                statement = statement.order_by(
                    DataContractVersionRow.created_at.desc(),
                    DataContractVersionRow.id.desc(),
                )
            row = await session.scalar(statement.limit(1))
            return _contract(row) if row is not None else None

    async def get_pipeline(self, unit_key: str, pipeline_key: str) -> DataPipeline | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            row = await session.scalar(
                select(DataPipelineRow).where(
                    DataPipelineRow.owner_unit_id == unit_id,
                    DataPipelineRow.key == pipeline_key,
                )
            )
            return _pipeline(row) if row is not None else None

    async def start_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                pipeline = await session.get(DataPipelineRow, run.pipeline_id)
                if pipeline is None or pipeline.owner_unit_id != unit_id:
                    raise DataReferenceError("pipeline is outside the authorized scope")
                if pipeline.status != "active":
                    raise DataStateError("only an active pipeline can start")
                source = await session.get(DataSourceRow, pipeline.source_id)
                if source is None or source.status != "active":
                    raise DataStateError("only an active source can be ingested")
                contract = await session.scalar(
                    select(DataContractVersionRow)
                    .where(DataContractVersionRow.asset_id == pipeline.output_asset_id)
                    .order_by(
                        DataContractVersionRow.created_at.desc(),
                        DataContractVersionRow.id.desc(),
                    )
                    .limit(1)
                )
                if contract is None:
                    raise DataReferenceError("pipeline output requires a published data contract")
                scope = f"data:run:start:{pipeline.id}:{command.actor_id}"
                replay = await self._replay_id(session, scope, command)
                if replay is not None:
                    row = await session.get(DataIngestionRunRow, replay)
                    if row is None:
                        raise DataReferenceError("idempotent run is no longer available")
                    return _run(row)
                event = _event("kya.data.run.started.v1", "data_run", run.id, unit_id, command)
                event.payload.update(
                    {
                        "unit_key": unit_key,
                        "pipeline_id": str(pipeline.id),
                        "pipeline_key": pipeline.key,
                        "source_id": str(source.id),
                        "source_configuration": source.configuration,
                        "asset_id": str(pipeline.output_asset_id),
                        "contract_id": str(contract.id),
                    }
                )
                session.add_all(
                    [
                        DataIngestionRunRow(
                            id=run.id,
                            pipeline_id=run.pipeline_id,
                            triggered_by=run.triggered_by,
                            status=run.status.value,
                            started_at=run.started_at,
                            metrics={},
                        ),
                        event,
                    ]
                )
                self._remember(session, scope, command, run.id)
        except IntegrityError as error:
            raise DataConflictError("ingestion run already exists") from error
        return run

    async def get_run(self, unit_key: str, run_id: UUID) -> IngestionRun | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            row = await session.scalar(
                select(DataIngestionRunRow)
                .join(DataPipelineRow, DataPipelineRow.id == DataIngestionRunRow.pipeline_id)
                .where(
                    DataIngestionRunRow.id == run_id,
                    DataPipelineRow.owner_unit_id == unit_id,
                )
            )
            return _run(row) if row is not None else None

    async def get_run_report(self, unit_key: str, run_id: UUID) -> IngestionRunReport | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            record = (
                await session.execute(
                    select(DataIngestionRunRow, DataPipelineRow)
                    .join(DataPipelineRow, DataPipelineRow.id == DataIngestionRunRow.pipeline_id)
                    .where(
                        DataIngestionRunRow.id == run_id,
                        DataPipelineRow.owner_unit_id == unit_id,
                    )
                )
            ).first()
            if record is None:
                return None
            run_row, pipeline_row = record
            snapshot_row = await session.scalar(
                select(DataSnapshotRow).where(DataSnapshotRow.run_id == run_id)
            )
            quality_results: tuple[QualityResult, ...] = ()
            if snapshot_row is not None:
                quality_rows = await session.scalars(
                    select(DataQualityResultRow)
                    .where(DataQualityResultRow.snapshot_id == snapshot_row.id)
                    .order_by(DataQualityResultRow.rule_key)
                )
                quality_results = tuple(
                    QualityResult(
                        row.rule_key,
                        QualityStatus(row.status),
                        cast(dict[str, object] | None, row.observed),
                    )
                    for row in quality_rows
                )
            return IngestionRunReport(
                run=_run(run_row),
                pipeline_key=pipeline_row.key,
                snapshot=_snapshot(snapshot_row) if snapshot_row is not None else None,
                quality_results=quality_results,
            )

    async def complete_run(
        self, unit_key: str, completion: RunCompletion, *, command: CommandMetadata
    ) -> RunCompletion:
        try:
            async with self._sessions() as session, session.begin():
                unit_id = await self._required_unit_id(session, unit_key)
                row = await session.get(DataIngestionRunRow, completion.run.id)
                if row is None:
                    raise DataReferenceError("ingestion run does not exist")
                pipeline = await session.get(DataPipelineRow, row.pipeline_id)
                if pipeline is None or pipeline.owner_unit_id != unit_id:
                    raise DataReferenceError("run is outside the authorized scope")
                scope = f"data:run:complete:{row.id}:{command.actor_id}"
                replay = await self._replay_id(session, scope, command)
                if replay is not None:
                    snapshot_row = await session.get(DataSnapshotRow, replay)
                    if snapshot_row is None:
                        raise DataReferenceError("idempotent snapshot is no longer available")
                    return RunCompletion(_run(row), _snapshot(snapshot_row))
                if row.status != "started":
                    raise DataStateError("only a started run can complete")
                if (
                    completion.run.pipeline_id != row.pipeline_id
                    or completion.run.started_at != row.started_at
                ):
                    raise DataReferenceError("run completion does not match the persisted run")
                snapshot = completion.snapshot
                if snapshot.run_id != row.id or snapshot.asset_id != pipeline.output_asset_id:
                    raise DataReferenceError("snapshot does not match its run output")
                contract = await session.get(DataContractVersionRow, snapshot.contract_id)
                if contract is None or contract.asset_id != snapshot.asset_id:
                    raise DataReferenceError("snapshot contract does not belong to its asset")
                valid_rules = {cast(str, rule["key"]) for rule in contract.quality_rules}
                if any(result.rule_key not in valid_rules for result in completion.quality_results):
                    raise DataReferenceError("quality result is absent from the snapshot contract")
                input_rows: list[DataSnapshotRow] = []
                for input_id in completion.input_snapshot_ids:
                    input_row = await session.get(DataSnapshotRow, input_id)
                    if input_row is None:
                        raise DataReferenceError("lineage input snapshot does not exist")
                    input_rows.append(input_row)
                row.status = completion.run.status.value
                row.completed_at = completion.run.completed_at
                snapshot_row = DataSnapshotRow(
                    id=snapshot.id,
                    asset_id=snapshot.asset_id,
                    run_id=snapshot.run_id,
                    contract_id=snapshot.contract_id,
                    storage_provider=snapshot.storage.provider,
                    storage_container=snapshot.storage.container,
                    object_key=snapshot.storage.object_key,
                    object_version=snapshot.storage.version_id,
                    content_digest=snapshot.content_digest,
                    media_type=snapshot.media_type,
                    row_count=snapshot.row_count,
                    byte_size=snapshot.byte_size,
                    observed_at=snapshot.observed_at,
                )
                session.add(snapshot_row)
                await session.flush()
                document_rows = [
                    DataContentDocumentRow(
                        id=document.id,
                        snapshot_id=snapshot.id,
                        ordinal=document.ordinal,
                        source_uri=document.source_uri,
                        canonical_uri=document.canonical_uri,
                        title=document.title,
                        language=document.language,
                        body_digest=document.body_digest,
                        content_trust=document.content_trust,
                    )
                    for document in completion.content_documents
                ]
                if document_rows:
                    session.add_all(document_rows)
                    await session.flush()
                session.add_all(
                    [
                        *(
                            DataQualityResultRow(
                                snapshot_id=snapshot.id,
                                rule_key=result.rule_key,
                                status=result.status.value,
                                observed=result.observed,
                            )
                            for result in completion.quality_results
                        ),
                        *(
                            DataLineageEdgeRow(
                                run_id=row.id,
                                input_snapshot_id=input_row.id,
                                output_snapshot_id=snapshot.id,
                            )
                            for input_row in input_rows
                        ),
                        *(
                            DataContentChunkRow(
                                id=chunk.id,
                                document_id=document.id,
                                ordinal=chunk.ordinal,
                                text=chunk.text,
                                char_start=chunk.char_start,
                                char_end=chunk.char_end,
                                content_digest=chunk.digest,
                            )
                            for document in completion.content_documents
                            for chunk in document.chunks
                        ),
                        _event("kya.data.run.completed.v1", "data_run", row.id, unit_id, command),
                    ]
                )
                self._remember(session, scope, command, snapshot.id)
        except IntegrityError as error:
            raise DataConflictError("run completion conflicts with existing evidence") from error
        return completion

    async def fail_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        async with self._sessions() as session, session.begin():
            unit_id = await self._required_unit_id(session, unit_key)
            row = await session.get(DataIngestionRunRow, run.id)
            if row is None:
                raise DataReferenceError("ingestion run does not exist")
            pipeline = await session.get(DataPipelineRow, row.pipeline_id)
            if pipeline is None or pipeline.owner_unit_id != unit_id:
                raise DataReferenceError("run is outside the authorized scope")
            scope = f"data:run:fail:{row.id}:{command.actor_id}"
            replay = await self._replay_id(session, scope, command)
            if replay is not None:
                return _run(row)
            if row.status != "started":
                raise DataStateError("only a started run can fail")
            row.status = run.status.value
            row.completed_at = run.completed_at
            row.error_code = run.error_code
            session.add(_event("kya.data.run.failed.v1", "data_run", row.id, unit_id, command))
            self._remember(session, scope, command, row.id)
        return run

    async def list_snapshots(
        self, unit_key: str, asset_key: str, *, limit: int
    ) -> Sequence[DataSnapshot]:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return ()
            rows = await session.scalars(
                select(DataSnapshotRow)
                .join(DataAssetRow, DataAssetRow.id == DataSnapshotRow.asset_id)
                .where(DataAssetRow.owner_unit_id == unit_id, DataAssetRow.key == asset_key)
                .order_by(DataSnapshotRow.observed_at.desc(), DataSnapshotRow.id.desc())
                .limit(limit)
            )
            return tuple(_snapshot(row) for row in rows)

    async def trace_lineage(self, unit_key: str, snapshot_id: UUID) -> SnapshotLineage | None:
        async with self._sessions() as session:
            unit_id = await self._unit_id(session, unit_key)
            if unit_id is None:
                return None
            snapshot_exists = await session.scalar(
                select(DataSnapshotRow.id)
                .join(DataAssetRow, DataAssetRow.id == DataSnapshotRow.asset_id)
                .where(
                    DataSnapshotRow.id == snapshot_id,
                    DataAssetRow.owner_unit_id == unit_id,
                )
            )
            if snapshot_exists is None:
                return None
            input_ids = await session.scalars(
                select(DataLineageEdgeRow.input_snapshot_id)
                .where(DataLineageEdgeRow.output_snapshot_id == snapshot_id)
                .order_by(DataLineageEdgeRow.input_snapshot_id)
            )
            output_ids = await session.scalars(
                select(DataLineageEdgeRow.output_snapshot_id)
                .where(DataLineageEdgeRow.input_snapshot_id == snapshot_id)
                .order_by(DataLineageEdgeRow.output_snapshot_id)
            )
            return SnapshotLineage(snapshot_id, tuple(input_ids), tuple(output_ids))

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
            raise DataReferenceError("organizational unit does not exist")
        return unit_id

    @staticmethod
    async def _replay_id(
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
            raise DataConflictError("idempotency key already belongs to another request")
        entity_id = record.response_body.get("id")
        if not isinstance(entity_id, str):
            raise DataConflictError("idempotency evidence is invalid")
        return UUID(entity_id)

    @staticmethod
    def _remember(
        session: AsyncSession,
        scope: str,
        command: CommandMetadata,
        entity_id: UUID,
    ) -> None:
        session.add(
            IdempotencyRecord(
                scope=scope,
                idempotency_key=command.idempotency_key,
                request_hash=command.request_hash,
                response_status=201,
                response_body={"id": str(entity_id)},
                expires_at=command.expires_at,
            )
        )


__all__ = ["SqlAlchemyDataRepository"]
