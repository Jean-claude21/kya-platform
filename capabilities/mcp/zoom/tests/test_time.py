from __future__ import annotations

import pytest

from kya_zoom_mcp.time import DateTimeFormatError, normalize_start_time


def test_lome_timezone_is_safely_mapped_to_utc() -> None:
    start_time, timezone = normalize_start_time("2026-09-21T10:00:00", "Africa/Lome")

    assert start_time == "2026-09-21T10:00:00"
    assert timezone == "UTC"


def test_offset_datetime_is_converted_to_utc() -> None:
    start_time, _ = normalize_start_time("2026-09-21T12:00:00+02:00", "Europe/Paris")

    assert start_time == "2026-09-21T10:00:00Z"


def test_date_without_time_is_rejected() -> None:
    with pytest.raises(DateTimeFormatError, match="explicit time"):
        normalize_start_time("2026-09-21", "Africa/Lome")
