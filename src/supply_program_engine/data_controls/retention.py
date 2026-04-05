from __future__ import annotations

from datetime import timedelta

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.data_controls.models import iso_now, parse_iso
from supply_program_engine.data_controls.redaction import apply_reply_redaction, redaction_overlays
from supply_program_engine.data_controls.subject_requests import subject_request_states
from supply_program_engine.models import EventType


def _erasure_request_for_entity(entity_id: str) -> dict | None:
    for request in subject_request_states().values():
        if request.get("entity_id") != entity_id:
            continue
        if request.get("request_type") != "erasure":
            continue
        if request.get("status") not in {"approved", "completed"}:
            continue
        return request
    return None


def run_once(limit: int = 50) -> dict:
    processed = 0
    reviewed = 0
    redacted = 0
    skipped_duplicates = 0
    overlays = redaction_overlays()

    for rec in ledger.read():
        if processed >= limit:
            break

        if rec.get("event_type") != EventType.REPLY_RECEIVED.value:
            continue

        processed += 1
        payload = rec.get("payload") or {}
        reply_key = payload.get("reply_key")
        entity_id = rec.get("entity_id") or "unknown"
        if not reply_key or reply_key in overlays:
            skipped_duplicates += 1
            continue

        received_at = parse_iso(payload.get("received_at"))
        erasure_request = _erasure_request_for_entity(entity_id)

        reason = None
        subject_request_id = None
        if erasure_request is not None:
            reason = "subject_request_erasure"
            subject_request_id = erasure_request.get("request_id")
        elif received_at is not None:
            retention_cutoff = received_at + timedelta(days=settings.REPLY_TEXT_RETENTION_DAYS)
            compare_at = parse_iso(iso_now())
            assert compare_at is not None
            if compare_at >= retention_cutoff:
                reason = "retention_window_elapsed"

        if reason is None:
            continue

        review_event_id = ledger.generate_event_id(
            {
                "event_type": EventType.RETENTION_REVIEWED.value,
                "reply_key": reply_key,
                "reason": reason,
                "subject_request_id": subject_request_id,
            }
        )
        if not ledger.exists(review_event_id):
            ledger.append(
                {
                    "event_id": review_event_id,
                    "event_type": EventType.RETENTION_REVIEWED.value,
                    "correlation_id": rec.get("correlation_id") or "retention-runner",
                    "entity_id": entity_id,
                    "payload": {
                        "reply_key": reply_key,
                        "target_event_id": rec.get("event_id"),
                        "reviewed_at": rec.get("ts") or payload.get("received_at"),
                        "policy_name": "reply_text_retention_v1",
                        "action": "redacted",
                        "reason": reason,
                        "subject_request_id": subject_request_id,
                    },
                }
            )
            reviewed += 1

        result = apply_reply_redaction(
            reply_key=reply_key,
            entity_id=entity_id,
            target_event_id=rec.get("event_id") or reply_key,
            reason=reason,
            source="retention_runner",
            correlation_id=rec.get("correlation_id") or "retention-runner",
            subject_request_id=subject_request_id,
        )
        if result["status"] == "recorded":
            redacted += 1
        else:
            skipped_duplicates += 1

    return {
        "processed": processed,
        "reviewed": reviewed,
        "redacted": redacted,
        "skipped_duplicates": skipped_duplicates,
    }
