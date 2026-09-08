"""KYA Data persistence is scoped, replay-safe and evidential."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.application.data import (
    CommandMetadata,
    DataConflictError,
    DataReferenceError,
    RunCompletion,
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
from kya_platform.infrastructure.database.data import SqlAlchemyDataRepository
from kya_platform.infrastructure.database.models import (
    CatalogArtifact,
    CatalogArtifactVersion,
    DataAssetRow,
    DataContractVersionRow,
    DataIngestionRunRow,
    DataPipelineRow,
    DataSnapshotRow,
    DataSourceRow,
    IdempotencyRecord,
    OutboxEvent,
)

UNIT = UUID("01993480-0000-7000-8000-000000000001")
ACTOR = UUID("01993480-0000-7000-8000-000000000002")
SOURCE = UUID("01993480-0000-7000-8000-000000000003")
ASSET = UUID("01993480-0000-7000-8000-000000000004")
CONTRACT = UUID("01993480-0000-7000-8000-000000000005")
CONNECTOR = UUID("01993480-0000-7000-8000-000000000006")
CONNECTOR_VERSION = UUID("01993480-0000-7000-8000-000000000007")
PIPELINE = UUID("01993480-0000-7000-8000-000000000008")
RUN = UUID("01993480-0000-7000-8000-000000000009")
SNAPSHOT = UUID("01993480-0000-7000-8000-000000000010")
NOW = datetime(2026, 9, 7, 14, tzinfo=UTC)


class ScalarRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self.rows = list(rows)

    def __iter__(self) -> Iterable[object]:
        return iter(self.rows)


class ExecuteRows:
    def __init__(self, row: object | None) -> None:
        self.row = row

    def first(self) -> object | None:
        return self.row


class Session:
    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        scalar_rows: list[list[object]] | None = None,
        get_values: list[object | None] | None = None,
        execute_values: list[object | None] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalar_rows = scalar_rows or []
        self.get_values = get_values or []
        self.execute_values = execute_values or []
        self.added: list[object] = []
        self.flushes = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> Self:
        return self

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> ScalarRows:
        del statement
        return ScalarRows(self.scalar_rows.pop(0))

    async def get(self, model: object, identity: object) -> object | None:
        del model, identity
        return self.get_values.pop(0)

    async def execute(self, statement: object) -> ExecuteRows:
        del statement
        return ExecuteRows(self.execute_values.pop(0))

    async def flush(self) -> None:
        self.flushes += 1

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def repository(session: Session) -> SqlAlchemyDataRepository:
    return SqlAlchemyDataRepository(Sessions(session))  # type: ignore[arg-type]


def command() -> CommandMetadata:
    return CommandMetadata(
        ACTOR,
        UUID("01993480-0000-7000-8000-000000000099"),
        "data-command-000001",
        "a" * 64,
        datetime(2026, 9, 8, tzinfo=UTC),
    )


def source() -> DataSource:
    return DataSource(
        SOURCE,
        "market-api",
        "API marché",
        DataSourceKind.API,
        UNIT,
        secret_reference="infisical:data/market-api",
        status=DataStatus.ACTIVE,
    )


def source_row() -> DataSourceRow:
    item = source()
    return DataSourceRow(
        id=item.id,
        key=item.key,
        name=item.name,
        kind=item.kind.value,
        owner_unit_id=item.owner_unit_id,
        secret_reference=item.secret_reference,
        configuration=item.configuration,
        status=item.status.value,
        created_by=ACTOR,
    )


def asset() -> DataAsset:
    return DataAsset(
        ASSET,
        "market-prices-raw",
        "Prix bruts",
        UNIT,
        DataAssetLayer.RAW,
        DataClassification.INTERNAL,
        DataStatus.ACTIVE,
    )


def asset_row() -> DataAssetRow:
    item = asset()
    return DataAssetRow(
        id=item.id,
        key=item.key,
        name=item.name,
        owner_unit_id=item.owner_unit_id,
        layer=item.layer.value,
        classification=item.classification.value,
        status=item.status.value,
        created_by=ACTOR,
    )


def contract() -> DataContract:
    return DataContract(
        CONTRACT,
        ASSET,
        "1.0.0",
        {"type": "object"},
        "b" * 64,
        (QualityRule("price-required", "not-null", "price IS NOT NULL"),),
        60,
        30,
    )


def contract_row() -> DataContractVersionRow:
    item = contract()
    return DataContractVersionRow(
        id=item.id,
        asset_id=item.asset_id,
        version=item.version,
        schema_document=item.schema,
        quality_rules=[
            {
                "key": "price-required",
                "kind": "not-null",
                "expression": "price IS NOT NULL",
                "severity": "error",
            }
        ],
        freshness_minutes=60,
        retention_days=30,
        digest=item.digest,
        created_by=ACTOR,
    )


def pipeline() -> DataPipeline:
    return DataPipeline(
        PIPELINE,
        "collect-market-prices",
        "Collecte prix",
        UNIT,
        SOURCE,
        CONNECTOR_VERSION,
        ASSET,
        DataStatus.ACTIVE,
    )


def pipeline_row() -> DataPipelineRow:
    item = pipeline()
    return DataPipelineRow(
        id=item.id,
        key=item.key,
        name=item.name,
        owner_unit_id=item.owner_unit_id,
        source_id=item.source_id,
        connector_version_id=item.connector_version_id,
        output_asset_id=item.output_asset_id,
        status=item.status.value,
        created_by=ACTOR,
    )


def run_row(status: str = "started") -> DataIngestionRunRow:
    return DataIngestionRunRow(
        id=RUN,
        pipeline_id=PIPELINE,
        triggered_by=ACTOR,
        status=status,
        started_at=NOW,
        completed_at=None if status == "started" else NOW,
        metrics={},
    )


def snapshot() -> DataSnapshot:
    return DataSnapshot(
        SNAPSHOT,
        ASSET,
        RUN,
        CONTRACT,
        StorageObject("neon", "kya-data", "raw/market.json", "v1"),
        "c" * 64,
        "application/json",
        NOW,
        4,
        128,
    )


def snapshot_row() -> DataSnapshotRow:
    item = snapshot()
    return DataSnapshotRow(
        id=item.id,
        asset_id=item.asset_id,
        run_id=item.run_id,
        contract_id=item.contract_id,
        storage_provider=item.storage.provider,
        storage_container=item.storage.container,
        object_key=item.storage.object_key,
        object_version=item.storage.version_id,
        content_digest=item.content_digest,
        media_type=item.media_type,
        observed_at=item.observed_at,
        row_count=item.row_count,
        byte_size=item.byte_size,
    )


def connector_rows() -> tuple[CatalogArtifactVersion, CatalogArtifact]:
    artifact = CatalogArtifact(
        id=CONNECTOR,
        slug="market-connector",
        artifact_type="connector",
        name="Market Connector",
        owner_workspace_id=UNIT,
        business_owner_id=ACTOR,
        technical_owner_id=ACTOR,
        lifecycle="published",
    )
    version = CatalogArtifactVersion(
        id=CONNECTOR_VERSION,
        artifact_id=CONNECTOR,
        version="1.0.0",
        status="published",
        source_repository="https://github.com/kya/market",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={},
        inventory_digest="d" * 64,
        package_size=1,
        file_count=1,
        risk="low",
        created_by=ACTOR,
    )
    return version, artifact


@pytest.mark.asyncio
@pytest.mark.unit
async def test_lists_sources_assets_runs_and_snapshots_in_unit_scope() -> None:
    source_session = Session(scalar_values=[UNIT], scalar_rows=[[source_row()]])
    assert (await repository(source_session).list_sources("direction-cvsi", limit=10))[
        0
    ].id == SOURCE

    asset_session = Session(scalar_values=[UNIT], scalar_rows=[[asset_row()]])
    assert (await repository(asset_session).list_assets("direction-cvsi", limit=10))[0].id == ASSET

    run_session = Session(scalar_values=[UNIT, run_row()])
    assert await repository(run_session).get_run("direction-cvsi", RUN) == IngestionRun(
        RUN, PIPELINE, ACTOR, RunStatus.STARTED, NOW
    )

    snapshot_session = Session(scalar_values=[UNIT], scalar_rows=[[snapshot_row()]])
    records = await repository(snapshot_session).list_snapshots(
        "direction-cvsi", "market-prices-raw", limit=10
    )
    assert records[0].storage.version_id == "v1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_searches_and_resolves_governed_data_metadata() -> None:
    search_session = Session(scalar_values=[UNIT], scalar_rows=[[asset_row()]])
    matches = await repository(search_session).search_assets("direction-cvsi", "prix", limit=10)
    assert matches[0].key == "market-prices-raw"

    asset_session = Session(scalar_values=[UNIT, asset_row()])
    assert (
        await repository(asset_session).get_asset("direction-cvsi", "market-prices-raw")
    ) == asset()

    contract_session = Session(scalar_values=[UNIT, contract_row()])
    assert (
        await repository(contract_session).get_contract(
            "direction-cvsi", "market-prices-raw", version="1.0.0"
        )
    ) == contract()

    pipeline_session = Session(scalar_values=[UNIT, pipeline_row()])
    assert (
        await repository(pipeline_session).get_pipeline("direction-cvsi", "collect-market-prices")
    ) == pipeline()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_traces_only_a_snapshot_inside_the_active_unit() -> None:
    upstream = UUID("01993480-0000-7000-8000-000000000011")
    downstream = UUID("01993480-0000-7000-8000-000000000012")
    session = Session(
        scalar_values=[UNIT, SNAPSHOT],
        scalar_rows=[[upstream], [downstream]],
    )
    lineage = await repository(session).trace_lineage("direction-cvsi", SNAPSHOT)
    assert lineage is not None
    assert lineage.input_snapshot_ids == (upstream,)
    assert lineage.output_snapshot_ids == (downstream,)

    absent = Session(scalar_values=[UNIT, None])
    assert await repository(absent).trace_lineage("direction-cvsi", SNAPSHOT) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_unit_lists_are_empty() -> None:
    assert await repository(Session(scalar_values=[None])).list_sources("unknown", limit=10) == ()
    assert await repository(Session(scalar_values=[None])).list_assets("unknown", limit=10) == ()
    assert await repository(Session(scalar_values=[None])).get_run("unknown", RUN) is None
    assert (
        await repository(Session(scalar_values=[None])).list_snapshots("unknown", "asset", limit=10)
        == ()
    )
    assert (
        await repository(Session(scalar_values=[None])).search_assets("unknown", "asset", limit=10)
        == ()
    )
    assert await repository(Session(scalar_values=[None])).get_asset("unknown", "asset") is None
    assert await repository(Session(scalar_values=[None])).get_contract("unknown", "asset") is None
    assert (
        await repository(Session(scalar_values=[None])).get_pipeline("unknown", "pipeline") is None
    )
    assert (
        await repository(Session(scalar_values=[None])).trace_lineage("unknown", SNAPSHOT) is None
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_creates_source_and_asset_with_outbox_and_idempotency() -> None:
    source_session = Session(scalar_values=[UNIT, None])
    created_source = await repository(source_session).create_source(
        "direction-cvsi", source(), command=command()
    )
    assert created_source.id == SOURCE
    assert any(isinstance(item, OutboxEvent) for item in source_session.added)
    assert any(isinstance(item, IdempotencyRecord) for item in source_session.added)

    asset_session = Session(scalar_values=[UNIT, None])
    created_asset = await repository(asset_session).create_asset(
        "direction-cvsi", asset(), command=command()
    )
    assert created_asset.id == ASSET
    assert any(isinstance(item, DataAssetRow) for item in asset_session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_replays_existing_source_and_asset() -> None:
    evidence_source = IdempotencyRecord(
        scope="scope",
        idempotency_key=command().idempotency_key,
        request_hash=command().request_hash,
        response_status=201,
        response_body={"id": str(SOURCE)},
        expires_at=command().expires_at,
    )
    source_session = Session(scalar_values=[UNIT, evidence_source], get_values=[source_row()])
    assert (
        await repository(source_session).create_source(
            "direction-cvsi", source(), command=command()
        )
    ).id == SOURCE

    evidence_asset = IdempotencyRecord(
        scope="scope",
        idempotency_key=command().idempotency_key,
        request_hash=command().request_hash,
        response_status=201,
        response_body={"id": str(ASSET)},
        expires_at=command().expires_at,
    )
    asset_session = Session(scalar_values=[UNIT, evidence_asset], get_values=[asset_row()])
    assert (
        await repository(asset_session).create_asset("direction-cvsi", asset(), command=command())
    ).id == ASSET


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publishes_contract_and_restores_it_on_replay() -> None:
    session = Session(scalar_values=[UNIT, None], get_values=[asset_row()])
    result = await repository(session).publish_contract(
        "direction-cvsi", contract(), command=command()
    )
    assert result.quality_rules[0].key == "price-required"

    evidence = IdempotencyRecord(
        scope="scope",
        idempotency_key=command().idempotency_key,
        request_hash=command().request_hash,
        response_status=201,
        response_body={"id": str(CONTRACT)},
        expires_at=command().expires_at,
    )
    replay_session = Session(
        scalar_values=[UNIT, evidence], get_values=[asset_row(), contract_row()]
    )
    replayed = await repository(replay_session).publish_contract(
        "direction-cvsi", contract(), command=command()
    )
    assert replayed.freshness_minutes == 60


@pytest.mark.asyncio
@pytest.mark.unit
async def test_pipeline_requires_a_published_connector_version() -> None:
    valid = Session(
        scalar_values=[UNIT, None],
        get_values=[source_row(), asset_row()],
        execute_values=[connector_rows()],
    )
    result = await repository(valid).create_pipeline(
        "direction-cvsi", pipeline(), command=command()
    )
    assert result.connector_version_id == CONNECTOR_VERSION

    invalid_version, invalid_artifact = connector_rows()
    invalid_version.status = "draft"
    invalid = Session(
        scalar_values=[UNIT],
        get_values=[source_row(), asset_row()],
        execute_values=[(invalid_version, invalid_artifact)],
    )
    with pytest.raises(DataReferenceError, match="published connector"):
        await repository(invalid).create_pipeline("direction-cvsi", pipeline(), command=command())


@pytest.mark.asyncio
@pytest.mark.unit
async def test_starts_active_pipeline_and_rejects_paused_one() -> None:
    run = IngestionRun(RUN, PIPELINE, ACTOR, RunStatus.STARTED, NOW)
    valid = Session(
        scalar_values=[UNIT, contract_row(), None],
        get_values=[pipeline_row(), source_row()],
    )
    assert (await repository(valid).start_run("direction-cvsi", run, command=command())).id == RUN
    event = next(item for item in valid.added if isinstance(item, OutboxEvent))
    assert event.payload["contract_id"] == str(CONTRACT)
    assert event.payload["unit_key"] == "direction-cvsi"
    assert event.payload["source_configuration"] == {}

    paused = pipeline_row()
    paused.status = "paused"
    with pytest.raises(Exception, match="only an active pipeline"):
        await repository(Session(scalar_values=[UNIT], get_values=[paused])).start_run(
            "direction-cvsi", run, command=command()
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_completes_run_with_snapshot_quality_lineage_and_evidence() -> None:
    terminal = IngestionRun(
        RUN, PIPELINE, ACTOR, RunStatus.COMPLETED, NOW, datetime(2026, 9, 7, 14, 1, tzinfo=UTC)
    )
    input_snapshot = snapshot_row()
    input_snapshot.id = UUID("01993480-0000-7000-8000-000000000011")
    completion = RunCompletion(
        terminal,
        snapshot(),
        (QualityResult("price-required", QualityStatus.PASSED, {"nulls": 0}),),
        (input_snapshot.id,),
    )
    session = Session(
        scalar_values=[UNIT, None],
        get_values=[run_row(), pipeline_row(), contract_row(), input_snapshot],
    )

    result = await repository(session).complete_run("direction-cvsi", completion, command=command())

    assert result.snapshot.id == SNAPSHOT
    assert session.flushes == 1
    assert session.get_values == []
    assert any(isinstance(item, OutboxEvent) for item in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_completion_rejects_contract_from_another_asset() -> None:
    terminal = IngestionRun(RUN, PIPELINE, ACTOR, RunStatus.COMPLETED, NOW, NOW)
    wrong_contract = contract_row()
    wrong_contract.asset_id = UUID("01993480-0000-7000-8000-000000000090")
    session = Session(
        scalar_values=[UNIT, None],
        get_values=[run_row(), pipeline_row(), wrong_contract],
    )
    with pytest.raises(DataReferenceError, match="does not belong"):
        await repository(session).complete_run(
            "direction-cvsi",
            RunCompletion(terminal, snapshot()),
            command=command(),
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fails_only_a_started_scoped_run() -> None:
    failed = IngestionRun(RUN, PIPELINE, ACTOR, RunStatus.FAILED, NOW, NOW, "source-timeout")
    session = Session(scalar_values=[UNIT, None], get_values=[run_row(), pipeline_row()])
    result = await repository(session).fail_run("direction-cvsi", failed, command=command())
    assert result.error_code == "source-timeout"
    assert session.get_values == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_idempotency_rejects_a_key_reused_for_another_payload() -> None:
    evidence = IdempotencyRecord(
        scope="scope",
        idempotency_key=command().idempotency_key,
        request_hash="b" * 64,
        response_status=201,
        response_body={"id": str(SOURCE)},
        expires_at=command().expires_at,
    )
    session = Session(scalar_values=[evidence])
    with pytest.raises(DataConflictError, match="another request"):
        await SqlAlchemyDataRepository._replay_id(
            session,  # type: ignore[arg-type]
            "scope",
            command(),
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_missing_unit_is_a_reference_error() -> None:
    with pytest.raises(DataReferenceError, match="does not exist"):
        await SqlAlchemyDataRepository._required_unit_id(
            Session(scalar_values=[None]),  # type: ignore[arg-type]
            "missing",
        )
