"""Per-request context that propagates across asynchronous calls."""

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str | None:
    """Return the active request correlation identifier, if any."""

    return _correlation_id.get()


__all__ = ["_correlation_id", "current_correlation_id"]
