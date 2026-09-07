"""Data use cases remain transport- and vendor-independent."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from kya_platform.application.data import CommandMetadata, DataService, RunCompletion
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
    RunStatus,
    StorageObject,
)

IDENTIFIER = UUID("01993490-0000-7000-8000-000000000001")
NOW = datetime(2026, 9, 7, 15, tzinfo=UTC)


def command() -> CommandMetadata:
    return CommandMetadata(IDENTIFIER, IDENTIFIER, "data-service-command", "a" * 64, NOW)


@pytest.mark.unit
def test_command_metadata_rejects_unreliable_evidence() -> None:
    with pytest.raises(ValueError, match="16 to 200"):
        CommandMetadata(IDENTIFIER, IDENTIFIER, "short", "a" * 64, NOW)
    with pytest.raises(ValueError, match="SHA-256"):
        CommandMetadata(IDENTIFIER, IDENTIFIER, "data-service-command", "bad", NOW)
    with pytest.raises(ValueError, match="timezone"):
        CommandMetadata(
            IDENTIFIER,
            IDENTIFIER,
            "data-service-command",
            "a" * 64,
            datetime(2026, 9, 7),
        )


@pytest.mark.unit
def test_run_completion_rejects_duplicate_evidence() -> None:
    started = IngestionRun(IDENTIFIER, IDENTIFIER, IDENTIFIER, RunStatus.STARTED, NOW)
    snapshot = DataSnapshot(
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        StorageObject("neon", "data", "raw/item.json"),
        "c" * 64,
        "application/json",
        NOW,
    )
    with pytest.raises(ValueError, match="completed run"):
        RunCompletion(started, snapshot)
    completed = started.complete(NOW)
    duplicate = UUID("01993490-0000-7000-8000-000000000010")
    with pytest.raises(ValueError, match="input snapshots"):
        RunCompletion(completed, snapshot, input_snapshot_ids=(duplicate, duplicate))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_delegates_the_complete_data_protocol() -> None:
    source = DataSource(
        IDENTIFIER, "source", "Source", DataSourceKind.API, IDENTIFIER, status=DataStatus.ACTIVE
    )
    asset = DataAsset(
        IDENTIFIER,
        "asset",
        "Asset",
        IDENTIFIER,
        DataAssetLayer.RAW,
        DataClassification.INTERNAL,
    )
    contract = DataContract(IDENTIFIER, IDENTIFIER, "1.0.0", {"type": "object"}, "b" * 64)
    pipeline = DataPipeline(
        IDENTIFIER,
        "pipeline",
        "Pipeline",
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        DataStatus.ACTIVE,
    )
    started = IngestionRun(IDENTIFIER, IDENTIFIER, IDENTIFIER, RunStatus.STARTED, NOW)
    completed = started.complete(NOW)
    failed = started.fail(NOW, "source-timeout")
    snapshot = DataSnapshot(
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        IDENTIFIER,
        StorageObject("neon", "data", "raw/item.json"),
        "c" * 64,
        "application/json",
        NOW,
    )
    completion = RunCompletion(completed, snapshot)
    repository = AsyncMock()
    repository.list_sources.return_value = (source,)
    repository.create_source.return_value = source
    repository.list_assets.return_value = (asset,)
    repository.create_asset.return_value = asset
    repository.publish_contract.return_value = contract
    repository.create_pipeline.return_value = pipeline
    repository.start_run.return_value = started
    repository.get_run.return_value = started
    repository.complete_run.return_value = completion
    repository.fail_run.return_value = failed
    repository.list_snapshots.return_value = (snapshot,)
    service = DataService(repository)
    metadata = command()

    assert await service.list_sources("group", limit=10) == (source,)
    assert await service.create_source("group", source, command=metadata) == source
    assert await service.list_assets("group", limit=10) == (asset,)
    assert await service.create_asset("group", asset, command=metadata) == asset
    assert await service.publish_contract("group", contract, command=metadata) == contract
    assert await service.create_pipeline("group", pipeline, command=metadata) == pipeline
    assert await service.start_run("group", started, command=metadata) == started
    assert await service.get_run("group", IDENTIFIER) == started
    assert await service.complete_run("group", completion, command=metadata) == completion
    assert await service.fail_run("group", failed, command=metadata) == failed
    assert await service.list_snapshots("group", "asset", limit=10) == (snapshot,)
