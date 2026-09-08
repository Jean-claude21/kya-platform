"""Source-flow persistence remains atomic, replay-safe and schedulable."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.application.data import CommandMetadata
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSource,
    DataSourceKind,
    DataStatus,
    QualityRule,
)
from kya_platform.domain.source_lifecycle import IngestionSchedule, SourceFlowDraft
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    CatalogArtifact,
    CatalogArtifactVersion,
    DataAssetRow,
    DataContractVersionRow,
    DataIngestionRunRow,
    DataIngestionScheduleRow,
    DataPipelineRow,
    DataSnapshotRow,
    DataSourceFlowRow,
    DataSourceRow,
    IdempotencyRecord,
    OutboxEvent,
)
from kya_platform.infrastructure.database.source_lifecycle import (
    SqlAlchemySourceLifecycleRepository,
)

UNIT = UUID("019934c0-0000-7000-8000-000000000001")
ACTOR = UUID("019934c0-0000-7000-8000-000000000002")
SOURCE = UUID("019934c0-0000-7000-8000-000000000003")
ASSET = UUID("019934c0-0000-7000-8000-000000000004")
CONTRACT = UUID("019934c0-0000-7000-8000-000000000005")
CONNECTOR = UUID("019934c0-0000-7000-8000-000000000006")
CONNECTOR_VERSION = UUID("019934c0-0000-7000-8000-000000000007")
PIPELINE = UUID("019934c0-0000-7000-8000-000000000008")
SCHEDULE = UUID("019934c0-0000-7000-8000-000000000009")
RUN = UUID("019934c0-0000-7000-8000-000000000010")
SNAPSHOT = UUID("019934c0-0000-7000-8000-000000000011")
NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)


class ScalarRows:
    def __init__(self, values: Iterable[object]) -> None:
        self.values = tuple(values)

    def __iter__(self) -> Iterable[object]:
        return iter(self.values)


class ExecuteRows:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def first(self) -> object | None:
        return self.value


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

    async def get(self, model: object, identity: object, **kwargs: object) -> object | None:
        del model, identity, kwargs
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


def repository(session: Session) -> SqlAlchemySourceLifecycleRepository:
    return SqlAlchemySourceLifecycleRepository(Sessions(session))  # type: ignore[arg-type]


def command(key: str = "source-flow-command-0001") -> CommandMetadata:
    return CommandMetadata(ACTOR, ACTOR, key, "a" * 64, NOW.replace(day=9))


def source_row(status: str = "active") -> DataSourceRow:
    return DataSourceRow(
        id=SOURCE,
        key="solar-source",
        name="Solar source",
        kind="web",
        owner_unit_id=UNIT,
        system_artifact_id=CONNECTOR,
        configuration={"seed_url": "https://kya-energy.com/fr"},
        status=status,
        created_by=ACTOR,
    )


def asset_row(status: str = "active") -> DataAssetRow:
    return DataAssetRow(
        id=ASSET,
        key="solar-raw",
        name="Solar raw",
        owner_unit_id=UNIT,
        layer="raw",
        classification="public",
        status=status,
        created_by=ACTOR,
    )


def contract_row() -> DataContractVersionRow:
    return DataContractVersionRow(
        id=CONTRACT,
        asset_id=ASSET,
        version="1.0.0",
        schema_document={"type": "object"},
        quality_rules=[
            {
                "key": "pages-present",
                "kind": "minimum-count",
                "expression": "count > 0",
                "severity": "error",
            }
        ],
        digest="b" * 64,
        created_by=ACTOR,
    )


def pipeline_row(status: str = "active") -> DataPipelineRow:
    return DataPipelineRow(
        id=PIPELINE,
        key="solar",
        name="Solar",
        owner_unit_id=UNIT,
        source_id=SOURCE,
        connector_version_id=CONNECTOR_VERSION,
        output_asset_id=ASSET,
        status=status,
        created_by=ACTOR,
    )


def control_row(revision: int = 1) -> DataSourceFlowRow:
    return DataSourceFlowRow(pipeline_id=PIPELINE, revision=revision, updated_by=ACTOR)


def schedule_row(*, due: datetime = NOW, revision: int = 1) -> DataIngestionScheduleRow:
    return DataIngestionScheduleRow(
        id=SCHEDULE,
        pipeline_id=PIPELINE,
        interval_minutes=1440,
        next_run_at=due,
        enabled=True,
        revision=revision,
        created_by=ACTOR,
        updated_by=ACTOR,
    )


def connector_rows() -> tuple[CatalogArtifactVersion, CatalogArtifact]:
    artifact = CatalogArtifact(
        id=CONNECTOR,
        slug="kya-owned-web-connector",
        artifact_type="connector",
        name="Web connector",
        owner_workspace_id=UNIT,
        business_owner_id=ACTOR,
        technical_owner_id=ACTOR,
        lifecycle="published",
    )
    version = CatalogArtifactVersion(
        id=CONNECTOR_VERSION,
        artifact_id=CONNECTOR,
        version="0.1.0",
        status="published",
        source_repository="https://github.com/kya/web",
        source_commit="a" * 40,
        content_digest="b" * 64,
        manifest_digest="c" * 64,
        manifest={},
        inventory_digest="d" * 64,
        package_size=1,
        file_count=1,
        risk="controlled-write",
        created_by=ACTOR,
    )
    return version, artifact


def draft() -> SourceFlowDraft:
    source = DataSource(
        SOURCE,
        "solar-source",
        "Solar source",
        DataSourceKind.WEB,
        UNIT,
        configuration={"seed_url": "https://kya-energy.com/fr"},
        status=DataStatus.ACTIVE,
    )
    asset = DataAsset(
        ASSET,
        "solar-raw",
        "Solar raw",
        UNIT,
        DataAssetLayer.RAW,
        DataClassification.PUBLIC,
        DataStatus.ACTIVE,
    )
    return SourceFlowDraft(
        source,
        asset,
        DataContract(
            CONTRACT,
            ASSET,
            "1.0.0",
            {"type": "object"},
            "b" * 64,
            (QualityRule("pages-present", "minimum-count", "count > 0"),),
        ),
        DataPipeline(
            PIPELINE,
            "solar",
            "Solar",
            UNIT,
            SOURCE,
            UUID(int=0),
            ASSET,
            DataStatus.ACTIVE,
        ),
        "kya-owned-web-connector",
        "0.1.0",
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_configures_complete_flow_in_one_transaction() -> None:
    session = Session(scalar_values=[UNIT, None], execute_values=[connector_rows()])
    schedule = IngestionSchedule(SCHEDULE, PIPELINE, 1440, NOW)

    flow = await repository(session).configure(
        "group", draft(), schedule=schedule, command=command()
    )

    assert flow.pipeline.connector_version_id == CONNECTOR_VERSION
    assert flow.schedule is not None
    assert flow.schedule.pipeline_id == PIPELINE
    assert session.flushes == 2
    assert any(isinstance(item, DataSourceFlowRow) for item in session.added)
    assert any(isinstance(item, DataIngestionScheduleRow) for item in session.added)
    assert any(isinstance(item, IdempotencyRecord) for item in session.added)
    assert any(isinstance(item, OutboxEvent) for item in session.added)
    assert any(isinstance(item, AuditEvent) for item in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reads_health_without_storage_location() -> None:
    run = DataIngestionRunRow(
        id=RUN,
        pipeline_id=PIPELINE,
        triggered_by=ACTOR,
        status="completed",
        started_at=NOW,
        completed_at=NOW,
        metrics={},
    )
    snapshot = DataSnapshotRow(
        id=SNAPSHOT,
        asset_id=ASSET,
        run_id=RUN,
        contract_id=CONTRACT,
        storage_provider="neon",
        storage_container="private",
        object_key="raw/hidden.json",
        content_digest="c" * 64,
        media_type="application/json",
        observed_at=NOW,
    )
    session = Session(
        scalar_values=[
            UNIT,
            pipeline_row(),
            contract_row(),
            schedule_row(),
            run,
            snapshot,
        ],
        scalar_rows=[["passed", "warning"]],
        get_values=[pipeline_row(), control_row(), source_row(), asset_row()],
    )

    health = await repository(session).get_health("group", "solar")

    assert health is not None
    assert health.latest_run is not None
    assert health.latest_snapshot_id == SNAPSHOT
    assert health.quality_status == "warning"
    assert "hidden.json" not in repr(health)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_transition_updates_all_components_and_revision() -> None:
    pipeline = pipeline_row()
    control = control_row()
    source = source_row()
    asset = asset_row()
    session = Session(
        scalar_values=[UNIT, pipeline, None, UNIT, pipeline, contract_row(), None],
        get_values=[
            control,
            source,
            asset,
            pipeline,
            control,
            source,
            asset,
        ],
    )

    flow = await repository(session).transition(
        "group",
        "solar",
        DataStatus.PAUSED,
        expected_revision=1,
        command=command(),
    )

    assert source.status == asset.status == pipeline.status == "paused"
    assert flow.status is DataStatus.PAUSED
    assert flow.revision == 2
    assert any(isinstance(item, AuditEvent) for item in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_schedule_update_advances_both_revisions() -> None:
    pipeline = pipeline_row()
    control = control_row()
    existing = schedule_row()
    session = Session(
        scalar_values=[
            UNIT,
            pipeline,
            None,
            existing,
            UNIT,
            pipeline,
            contract_row(),
            existing,
        ],
        get_values=[control, pipeline, control, source_row(), asset_row()],
    )
    desired = IngestionSchedule(SCHEDULE, PIPELINE, 60, NOW.replace(hour=15), False)

    flow = await repository(session).put_schedule(
        "group",
        "solar",
        desired,
        expected_revision=1,
        command=command(),
    )

    assert flow.revision == 2
    assert flow.schedule is not None
    assert flow.schedule.interval_minutes == 60
    assert flow.schedule.enabled is False
    assert any(isinstance(item, AuditEvent) for item in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_claims_due_schedule_once_and_emits_worker_event() -> None:
    schedule = schedule_row(due=NOW.replace(hour=12))
    pipeline = pipeline_row()
    session = Session(
        scalar_values=[contract_row(), "group"],
        scalar_rows=[[schedule]],
        get_values=[pipeline, source_row()],
    )

    runs = await repository(session).claim_due_runs(now=NOW, limit=20)

    assert len(runs) == 1
    assert runs[0].pipeline_id == PIPELINE
    assert schedule.last_claimed_at == NOW.replace(hour=12)
    assert schedule.next_run_at > NOW
    event = next(item for item in session.added if isinstance(item, OutboxEvent))
    assert event.topic == "kya.data.run.started.v1"
    assert event.payload["scheduled_for"] == NOW.replace(hour=12).isoformat()
