from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
from typing import Iterator

from supply_program_engine.config import settings
from supply_program_engine.observability.context import span_attributes

_TRACING_INITIALIZED = False
_OTEL_MODULES: dict[str, object] | None = None


@dataclass
class _NoopSpan:
    name: str
    attributes: dict[str, object]

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.attributes["exception.type"] = exc.__class__.__name__
        self.attributes["exception.message"] = str(exc)

    def set_status(self, status: object) -> None:
        self.attributes["status"] = status


def _load_otel_modules() -> dict[str, object] | None:
    global _OTEL_MODULES
    if _OTEL_MODULES is not None:
        return _OTEL_MODULES

    try:
        trace = importlib.import_module("opentelemetry.trace")
        sdk_trace = importlib.import_module("opentelemetry.sdk.trace")
        resources = importlib.import_module("opentelemetry.sdk.resources")
        export = importlib.import_module("opentelemetry.sdk.trace.export")
    except Exception:
        _OTEL_MODULES = {}
        return None

    _OTEL_MODULES = {
        "trace": trace,
        "sdk_trace": sdk_trace,
        "resources": resources,
        "export": export,
    }
    return _OTEL_MODULES


def initialize_tracing() -> bool:
    global _TRACING_INITIALIZED

    if _TRACING_INITIALIZED:
        return tracing_enabled()

    if not settings.OTEL_ENABLED:
        _TRACING_INITIALIZED = True
        return False

    modules = _load_otel_modules()
    if not modules:
        _TRACING_INITIALIZED = True
        return False

    trace = modules["trace"]
    sdk_trace = modules["sdk_trace"]
    resources = modules["resources"]
    export = modules["export"]

    tracer_provider = sdk_trace.TracerProvider(
        resource=resources.Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    )

    if settings.OTEL_EXPORTER_TYPE == "console":
        span_processor = export.SimpleSpanProcessor(export.ConsoleSpanExporter())
        tracer_provider.add_span_processor(span_processor)

    trace.set_tracer_provider(tracer_provider)
    _TRACING_INITIALIZED = True
    return True


def tracing_enabled() -> bool:
    if not settings.OTEL_ENABLED:
        return False
    modules = _load_otel_modules()
    return bool(modules)


def reset_tracing() -> None:
    global _TRACING_INITIALIZED, _OTEL_MODULES
    _TRACING_INITIALIZED = False
    _OTEL_MODULES = None


def current_trace_ids() -> dict[str, str] | None:
    modules = _load_otel_modules()
    if not modules:
        return None

    trace = modules["trace"]
    span = trace.get_current_span()
    if span is None:
        return None

    context = span.get_span_context()
    if not context or not getattr(context, "is_valid", False):
        return None

    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
    }


@contextmanager
def trace_span(
    name: str,
    *,
    correlation_id: str | None = None,
    entity_id: str | None = None,
    event_type: str | None = None,
    task_type: str | None = None,
    provider_name: str | None = None,
    extra: dict[str, object] | None = None,
) -> Iterator[object]:
    initialize_tracing()
    attributes = span_attributes(
        correlation_id=correlation_id,
        entity_id=entity_id,
        event_type=event_type,
        task_type=task_type,
        provider_name=provider_name,
        extra=extra,
    )

    if not tracing_enabled():
        yield _NoopSpan(name=name, attributes=attributes)
        return

    trace = _OTEL_MODULES["trace"]  # type: ignore[index]
    tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span
