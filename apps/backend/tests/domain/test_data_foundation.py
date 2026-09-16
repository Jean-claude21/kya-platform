"""KYA Data Foundation domain invariants."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataSource,
    DataSourceKind,
    IngestionRun,
    QualityRule,
    RunStatus,
    StorageObject,
)

IDENTIFIER = UUID("01993460-0000-7000-8000-000000000001")
NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


@pytest.mark.unit
def test_source_keeps_only_an_opaque_secret_reference() -> None:
    source = DataSource(
        IDENTIFIER,
        "kya-public-site",
        "Site public KYA",
        DataSourceKind.WEB,
        IDENTIFIER,
        secret_reference="infisical:data/sources/kya-public-site",
    )

    assert source.secret_reference == "infisical:data/sources/kya-public-site"

    with pytest.raises(ValueError, match="not a URL"):
        DataSource(
            IDENTIFIER,
            "unsafe-source",
            "Unsafe",
            DataSourceKind.API,
            IDENTIFIER,
            secret_reference="https://user:password@example.test",
        )


@pytest.mark.unit
def test_source_configuration_is_non_secret_json_only() -> None:
    with pytest.raises(ValueError, match="credential"):
        DataSource(
            IDENTIFIER,
            "owned-web",
            "Site KYA",
            DataSourceKind.WEB,
            IDENTIFIER,
            configuration={"http": {"api_token": "must-not-be-here"}},
        )
    with pytest.raises(ValueError, match="JSON"):
        DataSource(
            IDENTIFIER,
            "owned-web",
            "Site KYA",
            DataSourceKind.WEB,
            IDENTIFIER,
            configuration={"hosts": {"kya-energy.com"}},
        )


@pytest.mark.unit
def test_asset_is_independent_from_any_single_source() -> None:
    asset = DataAsset(
        IDENTIFIER,
        "market-prices-raw",
        "Prix de marché bruts",
        IDENTIFIER,
        DataAssetLayer.RAW,
        DataClassification.INTERNAL,
    )

    assert asset.layer is DataAssetLayer.RAW
    assert not hasattr(asset, "source_id")


@pytest.mark.unit
def test_contract_rejects_duplicate_quality_rule_keys() -> None:
    rule = QualityRule("price-required", "not-null", "price IS NOT NULL")

    with pytest.raises(ValueError, match="must be unique"):
        DataContract(
            IDENTIFIER,
            IDENTIFIER,
            "1.0.0",
            {"type": "object"},
            "a" * 64,
            quality_rules=(rule, rule),
        )


@pytest.mark.unit
def test_run_transitions_are_terminal_and_timestamped() -> None:
    run = IngestionRun(IDENTIFIER, IDENTIFIER, IDENTIFIER, RunStatus.STARTED, NOW)
    completed = run.complete(datetime(2026, 9, 7, 12, 5, tzinfo=UTC))

    assert completed.status is RunStatus.COMPLETED
    with pytest.raises(ValueError, match="only a started run"):
        completed.fail(datetime(2026, 9, 7, 12, 6, tzinfo=UTC), "late-failure")


@pytest.mark.unit
def test_storage_reference_never_persists_a_signed_url() -> None:
    with pytest.raises(ValueError, match="must not contain a URL"):
        StorageObject("neon", "data", "https://storage.test/item?signature=secret")


@pytest.mark.unit
def test_invalid_names_versions_and_sizes_fail_before_persistence() -> None:
    with pytest.raises(ValueError, match="kebab-case"):
        DataAsset(
            IDENTIFIER,
            "Invalid Key",
            "Asset",
            IDENTIFIER,
            DataAssetLayer.RAW,
            DataClassification.INTERNAL,
        )
    with pytest.raises(ValueError, match="name is required"):
        DataSource(IDENTIFIER, "source", " ", DataSourceKind.API, IDENTIFIER)
    with pytest.raises(ValueError, match="SemVer"):
        DataContract(IDENTIFIER, IDENTIFIER, "latest", {"type": "object"}, "a" * 64)
    with pytest.raises(ValueError, match="digest"):
        DataContract(IDENTIFIER, IDENTIFIER, "1.0.0", {"type": "object"}, "invalid")
    with pytest.raises(ValueError, match="name is required"):
        DataPipeline(
            IDENTIFIER,
            "pipeline",
            " ",
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
        )
    with pytest.raises(ValueError, match="row count"):
        DataSnapshot(
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
            StorageObject("neon", "data", "raw/item.json"),
            "a" * 64,
            "application/json",
            NOW,
            row_count=-1,
        )
