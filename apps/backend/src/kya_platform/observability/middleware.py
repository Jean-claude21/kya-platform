"""Pure ASGI middleware for safe request correlation and access logs."""

import logging
from time import perf_counter
from uuid import UUID, uuid7

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kya_platform.observability.context import _correlation_id

LOGGER = logging.getLogger("kya_platform.request")
CORRELATION_HEADER = "X-Correlation-ID"


def _validated_correlation_id(candidate: str | None) -> str:
    if candidate is None:
        return str(uuid7())
    try:
        return str(UUID(candidate))
    except ValueError, AttributeError:
        return str(uuid7())


class CorrelationMiddleware:
    """Attach one safe correlation ID to context, state, response and logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        correlation_id = _validated_correlation_id(headers.get(CORRELATION_HEADER))
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        context_token = _correlation_id.set(correlation_id)
        started_at = perf_counter()
        response_status = 500

        async def send_with_correlation(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                MutableHeaders(scope=message).append(CORRELATION_HEADER, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            LOGGER.info(
                "request.completed",
                extra={
                    "correlation_id": correlation_id,
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status": response_status,
                    "duration_ms": duration_ms,
                },
            )
            _correlation_id.reset(context_token)


__all__ = ["CORRELATION_HEADER", "CorrelationMiddleware"]
