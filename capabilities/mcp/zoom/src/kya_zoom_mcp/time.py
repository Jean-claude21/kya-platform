"""Date and timezone normalization at the Zoom boundary."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZOOM_LOCAL_FORMAT = "%Y-%m-%dT%H:%M:%S"
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Zoom silently ignores these valid IANA names. Each substitute has the same
# offset throughout the year, so the requested instant is preserved.
ZOOM_TIMEZONE_SUBSTITUTES = {
    "Africa/Abidjan": "UTC",
    "Africa/Accra": "UTC",
    "Africa/Bamako": "UTC",
    "Africa/Banjul": "UTC",
    "Africa/Bissau": "UTC",
    "Africa/Conakry": "UTC",
    "Africa/Dakar": "UTC",
    "Africa/Freetown": "UTC",
    "Africa/Lome": "UTC",
    "Africa/Monrovia": "UTC",
    "Africa/Nouakchott": "UTC",
    "Africa/Ouagadougou": "UTC",
    "Africa/Sao_Tome": "UTC",
    "Atlantic/St_Helena": "UTC",
    "GMT": "UTC",
    "Greenwich": "UTC",
}
_SUBSTITUTES_BY_LOWER = {key.lower(): value for key, value in ZOOM_TIMEZONE_SUBSTITUTES.items()}


class DateTimeFormatError(ValueError):
    """A date or timezone cannot be represented safely by Zoom."""


def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise DateTimeFormatError(
            f"Unknown IANA timezone: {name!r}. Use a value such as Africa/Lome or UTC."
        ) from exc
    return name


def zoom_timezone(name: str) -> str:
    return _SUBSTITUTES_BY_LOWER.get(name.strip().lower(), name)


def normalize_start_time(raw: str, timezone: str) -> tuple[str, str]:
    validate_timezone(timezone)
    zoom_tz = zoom_timezone(timezone)
    value = raw.strip()
    if not value:
        raise DateTimeFormatError("start_time is required")
    if _DATE_ONLY.match(value):
        raise DateTimeFormatError("start_time must include an explicit time")

    candidate = value.replace(" ", "T")
    if candidate.endswith(("z", "Z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise DateTimeFormatError("start_time must be a valid ISO 8601 date-time") from exc

    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).strftime(ZOOM_LOCAL_FORMAT) + "Z", zoom_tz
    return parsed.strftime(ZOOM_LOCAL_FORMAT), zoom_tz
