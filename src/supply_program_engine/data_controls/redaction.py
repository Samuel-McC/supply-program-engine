from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.data_controls.models import RedactionState, iso_now
from supply_program_engine.models import EventType


def apply_reply_redaction(
    *,
    reply_key: str,
    entity_id: str,
    target_event_id: str,
    reason: str,
    source: str,
    correlation_id: str,
    actor: str | None = None,
    subject_request_id: str | None = None,
) -> dict[str, object]:
    payload = RedactionState(
        reply_key=reply_key,
        entity_id=entity_id,
        target_event_id=target_event_id,
        fields_redacted=["reply_text", "reply_text_snippet"],
        replacement_text=settings.REDACTION_PLACEHOLDER,
        reason=reason,
        source=source,
        applied_at=iso_now(),
        actor=actor,
        subject_request_id=subject_request_id,
    ).model_dump()

    event_id = ledger.generate_event_id(
        {
            "event_type": EventType.DATA_REDACTION_APPLIED.value,
            "reply_key": reply_key,
            "reason": reason,
            "subject_request_id": subject_request_id,
        }
    )
    if ledger.exists(event_id):
        return {"status": "duplicate", "event_id": event_id, "payload": payload}

    stored = ledger.append(
        {
            "event_id": event_id,
            "event_type": EventType.DATA_REDACTION_APPLIED.value,
            "correlation_id": correlation_id,
            "entity_id": entity_id,
            "payload": payload,
        }
    )
    return {"status": "recorded", "event_id": stored["event_id"], "payload": payload}


def redaction_overlays() -> dict[str, dict]:
    overlays: dict[str, dict] = {}
    for rec in ledger.read():
        if rec.get("event_type") != EventType.DATA_REDACTION_APPLIED.value:
            continue
        payload = rec.get("payload") or {}
        reply_key = payload.get("reply_key")
        if reply_key:
            overlays[reply_key] = payload
    return overlays


def sanitize_event_record(record: dict, overlays: dict[str, dict] | None = None) -> dict:
    payload = dict(record.get("payload") or {})
    overlays = overlays or redaction_overlays()

    reply_key = payload.get("reply_key")
    overlay = overlays.get(reply_key) if reply_key else None
    if overlay:
        if "reply_text" in payload:
            payload["reply_text"] = overlay.get("replacement_text", settings.REDACTION_PLACEHOLDER)
        if "reply_text_snippet" in payload:
            payload["reply_text_snippet"] = overlay.get("replacement_text", settings.REDACTION_PLACEHOLDER)
        payload["redacted"] = True
        payload["redaction_reason"] = overlay.get("reason")

    sanitized = dict(record)
    sanitized["payload"] = payload
    return sanitized


def sanitized_entity_timeline(entity_id: str) -> list[dict]:
    overlays = redaction_overlays()
    return [sanitize_event_record(rec, overlays) for rec in ledger.read(entity_id=entity_id)]
