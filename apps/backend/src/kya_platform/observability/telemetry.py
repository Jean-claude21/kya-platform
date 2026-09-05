"""Process-local OpenTelemetry providers with optional OTLP/HTTP export."""

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from kya_platform.config import Settings


def _headers(settings: Settings) -> dict[str, str] | None:
    configured = settings.otel_exporter_otlp_headers
    if configured is None:
        return None
    pairs: dict[str, str] = {}
    for item in configured.get_secret_value().split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip():
            pairs[key.strip()] = value.strip()
    return pairs or None


@dataclass(slots=True)
class TelemetryRuntime:
    """Own trace and metric providers so lifespan shutdown can flush them."""

    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    tracer: Tracer
    meter: Meter

    @classmethod
    def create(cls, settings: Settings) -> TelemetryRuntime:
        resource = Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": settings.version,
                "deployment.environment.name": settings.environment,
            }
        )
        tracer_provider = TracerProvider(resource=resource)
        metric_readers = []
        endpoint = settings.otel_exporter_otlp_endpoint
        if endpoint is not None:
            headers = _headers(settings)
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)
                )
            )
            metric_readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", headers=headers),
                    export_interval_millis=settings.otel_metric_export_interval_millis,
                )
            )
        meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
        scope = "kya_platform.http"
        return cls(
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            tracer=tracer_provider.get_tracer(scope),
            meter=meter_provider.get_meter(scope),
        )

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


__all__ = ["TelemetryRuntime"]
