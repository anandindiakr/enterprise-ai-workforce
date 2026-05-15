"""OpenTelemetry tracer setup for distributed tracing."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings

_initialized = False


def init_tracing() -> None:
    """Configure global tracer provider; safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
            )
        )
    except Exception:  # pragma: no cover - exporter optional
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer(name: str = "ai-workforce") -> trace.Tracer:
    if not _initialized:
        init_tracing()
    return trace.get_tracer(name)


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[trace.Span]:
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                pass
        yield s
