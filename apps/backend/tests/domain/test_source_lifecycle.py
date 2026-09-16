"""Source-flow aggregates keep ownership, linkage and schedule invariants."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSource,
    DataSourceKind,
)
from kya_platform.domain.source_lifecycle import IngestionSchedule, SourceFlow, SourceFlowDraft

IDENTIFIER = UUID("019934a0-0000-7000-8000-000000000001")
OTHER = UUID("019934a0-0000-7000-8000-000000000002")
NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)


def draft() -> SourceFlowDraft:
    source = DataSource(IDENTIFIER, "solar-source", "Solar", DataSourceKind.WEB, IDENTIFIER)
    asset = DataAsset(
        OTHER,
        "solar-raw",
        "Solar raw",
        IDENTIFIER,
        DataAssetLayer.RAW,
        DataClassification.PUBLIC,
    )
    return SourceFlowDraft(
        source,
        asset,
        DataContract(IDENTIFIER, asset.id, "1.0.0", {"type": "object"}, "a" * 64),
        DataPipeline(OTHER, "solar", "Solar", IDENTIFIER, source.id, OTHER, asset.id),
        "web-connector",
        "1.0.0",
    )


@pytest.mark.unit
def test_source_flow_draft_keeps_component_links_explicit() -> None:
    item = draft()
    assert item.pipeline.source_id == item.source.id
    assert item.contract.asset_id == item.asset.id


@pytest.mark.unit
def test_schedule_is_bounded_and_timezone_aware() -> None:
    assert IngestionSchedule(IDENTIFIER, OTHER, 15, NOW).interval_minutes == 15
    with pytest.raises(ValueError, match="between 15"):
        IngestionSchedule(IDENTIFIER, OTHER, 14, NOW)
    with pytest.raises(ValueError, match="timezone"):
        IngestionSchedule(IDENTIFIER, OTHER, 60, datetime(2026, 9, 8))


@pytest.mark.unit
def test_flow_rejects_divergent_component_state() -> None:
    item = draft()
    flow = SourceFlow(
        item.pipeline.key,
        item.source,
        item.asset,
        item.contract,
        item.pipeline,
        1,
    )
    assert flow.status.value == "draft"
    with pytest.raises(ValueError, match="match its pipeline"):
        SourceFlow(
            "another-flow",
            flow.source,
            flow.asset,
            flow.contract,
            flow.pipeline,
            flow.revision,
        )
