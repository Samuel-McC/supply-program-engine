from supply_program_engine.config import settings
from supply_program_engine.observability import current_trace_ids, reset_tracing, trace_span, tracing_enabled
from supply_program_engine.observability.context import span_attributes


def test_trace_span_is_safe_noop_when_otel_disabled(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)
    reset_tracing()

    with trace_span("test.span", correlation_id="c1", entity_id="e1", task_type="learning_run") as span:
        span.set_attribute("custom", "value")

    assert tracing_enabled() is False
    assert current_trace_ids() is None
    assert span.attributes["correlation_id"] == "c1"
    assert span.attributes["entity_id"] == "e1"
    assert span.attributes["task_type"] == "learning_run"
    assert span.attributes["custom"] == "value"


def test_span_attributes_compacts_known_fields():
    attrs = span_attributes(
        correlation_id="c1",
        entity_id="e1",
        event_type="candidate_ingested",
        task_type="enrichment_run",
        provider_name="mock",
        extra={"limit": 10, "ignored": None},
    )

    assert attrs == {
        "correlation_id": "c1",
        "entity_id": "e1",
        "event_type": "candidate_ingested",
        "task_type": "enrichment_run",
        "provider_name": "mock",
        "limit": 10,
    }
