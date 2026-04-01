from __future__ import annotations

from datetime import datetime, timezone

from supply_program_engine import ledger
from supply_program_engine.models import EventType, InboundReply
from supply_program_engine.projections import build_pipeline_state
from supply_program_engine.reply_triage.classifier import normalize_reply_text, reply_snippet


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_entity_id(reply: InboundReply) -> str | None:
    state = build_pipeline_state()

    if reply.entity_id:
        return reply.entity_id if reply.entity_id in state else None

    if reply.draft_id:
        draft_event = ledger.get(reply.draft_id)
        if draft_event and draft_event.get("entity_id"):
            return str(draft_event["entity_id"])

        for rec in ledger.read():
            payload = rec.get("payload") or {}
            if (
                rec.get("event_type") == EventType.OUTBOUND_DRAFT_CREATED.value
                and payload.get("draft_id") == reply.draft_id
                and rec.get("entity_id")
            ):
                return str(rec["entity_id"])

    if reply.provider_message_id:
        for event_type in (
            EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
            EventType.OUTBOUND_SENT.value,
        ):
            for rec in ledger.read():
                payload = rec.get("payload") or {}
                if (
                    rec.get("event_type") == event_type
                    and payload.get("provider_message_id") == reply.provider_message_id
                    and rec.get("entity_id")
                ):
                    return str(rec["entity_id"])

    return None


def build_reply_key(reply: InboundReply, entity_id: str) -> str:
    return ledger.generate_event_id(
        {
            "entity_id": entity_id,
            "draft_id": reply.draft_id,
            "provider_message_id": reply.provider_message_id,
            "received_at": reply.received_at,
            "normalized_reply_text": normalize_reply_text(reply.reply_text),
        }
    )


def build_received_payload(reply: InboundReply, reply_key: str) -> dict:
    received_at = reply.received_at or iso_now()
    return {
        "reply_key": reply_key,
        "draft_id": reply.draft_id,
        "provider_message_id": reply.provider_message_id,
        "received_at": received_at,
        "reply_text": reply.reply_text,
        "reply_text_snippet": reply_snippet(reply.reply_text),
        "metadata": reply.metadata,
    }
