"""KYA Intelligence domain invariants."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch, SignalStatus

IDENTIFIER = UUID("019934e0-0000-7000-8000-000000000001")
NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)


def test_watch_rejects_duplicate_asset_keys_and_short_query() -> None:
    with pytest.raises(ValueError, match="between 2 and 200"):
        IntelligenceWatch(IDENTIFIER, "solar", "Solar", " ", IDENTIFIER, IDENTIFIER)
    with pytest.raises(ValueError, match="unique"):
        IntelligenceWatch(
            IDENTIFIER,
            "solar",
            "Solar",
            "solaire",
            IDENTIFIER,
            IDENTIFIER,
            ("web", "web"),
        )


def test_signal_requires_consistent_acknowledgement() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        IntelligenceSignal(
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
            IDENTIFIER,
            f"kya:snapshot:{IDENTIFIER}:chunk:{IDENTIFIER}",
            "https://kya-energy.com",
            "Énergie solaire",
            NOW,
            "a" * 64,
            "b" * 64,
            status=SignalStatus.ACKNOWLEDGED,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"key": ""}, "key is required"),
        ({"name": " "}, "name is required"),
        ({"asset_keys": tuple(str(index) for index in range(51))}, "limited to 50"),
        ({"revision": 0}, "revision must be positive"),
    ],
)
def test_watch_validates_identity_bounds(overrides: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "id": IDENTIFIER,
        "key": "solar",
        "name": "Solar",
        "query": "solaire",
        "owner_unit_id": IDENTIFIER,
        "created_by": IDENTIFIER,
    }
    with pytest.raises(ValueError, match=message):
        IntelligenceWatch(**(values | overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"citation_id": "external"}, "KYA citation"),
        ({"source_uri": "http://example.com"}, "HTTPS"),
        ({"excerpt": " "}, "excerpt is required"),
        ({"revision": 0}, "revision must be positive"),
    ],
)
def test_signal_validates_evidence(overrides: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "id": IDENTIFIER,
        "watch_id": IDENTIFIER,
        "chunk_id": IDENTIFIER,
        "snapshot_id": IDENTIFIER,
        "citation_id": f"kya:snapshot:{IDENTIFIER}:chunk:{IDENTIFIER}",
        "source_uri": "https://kya-energy.com",
        "excerpt": "Énergie solaire",
        "observed_at": NOW,
        "snapshot_digest": "a" * 64,
        "page_digest": "b" * 64,
    }
    with pytest.raises(ValueError, match=message):
        IntelligenceSignal(**(values | overrides))  # type: ignore[arg-type]
