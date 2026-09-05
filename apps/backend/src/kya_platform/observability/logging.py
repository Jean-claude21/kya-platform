"""Structured JSON logs with recursive secret redaction."""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import SecretStr

from kya_platform.observability.context import current_correlation_id

REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|client[_-]?secret|database[_-]?url)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|client[_-]?secret|database[_-]?url)"
    r"\s*([:=])\s*([^\s,;]+)"
)
_URL_PASSWORD = re.compile(r"(?P<prefix>\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@]+@", re.I)
_STANDARD_LOG_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


def redact_text(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", value)
    return _URL_PASSWORD.sub(lambda match: f"{match.group('prefix')}{REDACTED}@", value)


def redact(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-safe copy with sensitive values removed recursively."""

    if key is not None and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


class SafeJsonFormatter(logging.Formatter):
    """Format standard and extra fields as one redacted JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        correlation_id = current_correlation_id()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_FIELDS and key not in {"message", "asctime"}:
                payload[key] = redact(value, key=key)
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Install the KYA formatter once on the process root logger."""

    root = logging.getLogger()
    if any(getattr(handler, "_kya_safe_handler", False) for handler in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJsonFormatter())
    handler._kya_safe_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)


__all__ = ["REDACTED", "SafeJsonFormatter", "configure_logging", "redact", "redact_text"]
