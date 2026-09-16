"""Pure ASGI middleware for safe request correlation and access logs."""

import logging
from contextlib import nullcontext
from time import perf_counter
from uuid import UUID, uuid7

from opentelemetry.metrics import Meter
from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
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

    def __init__(
        self, app: ASGIApp, *, tracer: Tracer | None = None, meter: Meter | None = None
    ) -> None:
        self.app = app
        self.tracer = tracer
        self.request_counter = (
            meter.create_counter(
                "kya.http.server.requests",
                unit="{request}",
                description="Completed KYA Platform HTTP requests",
            )
            if meter is not None
            else None
        )
        self.duration_histogram = (
            meter.create_histogram(
                "kya.http.server.duration",
                unit="ms",
                description="KYA Platform HTTP request duration",
            )
            if meter is not None
            else None
        )

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

        is_health_probe = scope["path"].startswith("/api/v1/health/")
        span_context = (
            self.tracer.start_as_current_span(
                f"{scope['method']} {scope['path']}",
                kind=SpanKind.SERVER,
                attributes={
                    "http.request.method": scope["method"],
                    "url.path": scope["path"],
                    "kya.correlation_id": correlation_id,
                },
            )
            if self.tracer is not None and not is_health_probe
            else nullcontext(None)
        )
        try:
            with span_context as span:
                try:
                    await self.app(scope, receive, send_with_correlation)
                finally:
                    if span is not None:
                        span.set_attribute("http.response.status_code", response_status)
                        if response_status >= 500:
                            span.set_status(Status(StatusCode.ERROR))
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            metric_attributes = {
                "http.request.method": scope["method"],
                "http.response.status_code": response_status,
            }
            if self.request_counter is not None:
                self.request_counter.add(1, metric_attributes)
            if self.duration_histogram is not None:
                self.duration_histogram.record(duration_ms, metric_attributes)
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
