from __future__ import annotations

from supply_program_engine.data_controls.redaction import sanitized_entity_timeline
from supply_program_engine.projections import build_pipeline_state


def build_entity_export(entity_id: str) -> dict[str, object]:
    state = build_pipeline_state()
    entity = state.get(entity_id)
    if entity is None:
        raise ValueError("entity_not_found")

    timeline = sanitized_entity_timeline(entity_id)
    event_summary = [
        {
            "event_id": record.get("event_id"),
            "event_type": record.get("event_type"),
            "correlation_id": record.get("correlation_id"),
            "ts": record.get("ts"),
            "payload": record.get("payload"),
        }
        for record in timeline
    ]

    return {
        "entity": entity.model_dump(),
        "event_summary": event_summary,
        "suppression_state": list(entity.active_suppressions),
        "subject_requests": list(entity.subject_request_summaries),
        "redaction_state": {
            "reply_text_redacted": entity.reply_text_redacted,
            "reply_text_redacted_at": entity.reply_text_redacted_at,
            "retention_status": entity.retention_status,
            "retention_last_reviewed_at": entity.retention_last_reviewed_at,
        },
    }
