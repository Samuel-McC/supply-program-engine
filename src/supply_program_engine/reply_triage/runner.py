from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import EventType, InboundReply
from supply_program_engine.observability import trace_span
from supply_program_engine.reply_triage.classifier import classify_reply
from supply_program_engine.reply_triage.ingest import build_received_payload, build_reply_key, resolve_entity_id

log = get_logger("supply_program_engine")


def _event_id(event_type: EventType, reply_key: str) -> str:
    return ledger.generate_event_id({"event_type": event_type.value, "reply_key": reply_key})


def _derived_event_type(classification: str) -> EventType | None:
    if classification == "interested":
        return EventType.LEAD_INTERESTED
    if classification == "not_interested":
        return EventType.LEAD_REJECTED
    if classification == "unsubscribe":
        return EventType.UNSUBSCRIBE_RECORDED
    return None


def process_reply(reply: InboundReply, correlation_id: str | None = None) -> dict:
    cid = correlation_id or generate_correlation_id()
    entity_id = resolve_entity_id(reply)
    if not entity_id:
        raise ValueError("unable_to_resolve_entity_id")

    with trace_span(
        "runner.reply_triage.process",
        correlation_id=cid,
        entity_id=entity_id,
        task_type="reply_triage",
        extra={"draft_id": reply.draft_id, "provider_message_id": reply.provider_message_id},
    ):
        reply_key = build_reply_key(reply, entity_id)
        emitted_event_ids: list[str] = []
        received_payload = build_received_payload(reply, reply_key)
        received_event_id = _event_id(EventType.REPLY_RECEIVED, reply_key)

        if not ledger.exists(received_event_id):
            ledger.append(
                {
                    "event_id": received_event_id,
                    "event_type": EventType.REPLY_RECEIVED.value,
                    "correlation_id": cid,
                    "entity_id": entity_id,
                    "payload": received_payload,
                }
            )
            emitted_event_ids.append(received_event_id)

        try:
            with trace_span(
                "runner.reply_triage.classify",
                correlation_id=cid,
                entity_id=entity_id,
                event_type=EventType.REPLY_CLASSIFIED.value,
                extra={"reply_key": reply_key},
            ):
                result = classify_reply(reply.reply_text)
            classified_event_id = _event_id(EventType.REPLY_CLASSIFIED, reply_key)
            classified_payload = {
                "reply_key": reply_key,
                "draft_id": reply.draft_id,
                "provider_message_id": reply.provider_message_id,
                "received_at": received_payload["received_at"],
                "reply_text_snippet": received_payload["reply_text_snippet"],
                "classification": result.classification,
                "matched_phrase": result.matched_phrase,
            }

            if not ledger.exists(classified_event_id):
                ledger.append(
                    {
                        "event_id": classified_event_id,
                        "event_type": EventType.REPLY_CLASSIFIED.value,
                        "correlation_id": cid,
                        "entity_id": entity_id,
                        "payload": classified_payload,
                    }
                )
                emitted_event_ids.append(classified_event_id)

            outcome_event_type = _derived_event_type(result.classification)
            outcome_event_id = None
            if outcome_event_type is not None:
                outcome_event_id = _event_id(outcome_event_type, reply_key)
                if not ledger.exists(outcome_event_id):
                    ledger.append(
                        {
                            "event_id": outcome_event_id,
                            "event_type": outcome_event_type.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": classified_payload,
                        }
                    )
                    emitted_event_ids.append(outcome_event_id)

            log.info(
                "reply_triage_processed",
                extra={
                    "correlation_id": cid,
                    "entity_id": entity_id,
                    "reply_key": reply_key,
                    "classification": result.classification,
                },
            )

            return {
                "status": "processed" if emitted_event_ids else "duplicate",
                "entity_id": entity_id,
                "reply_key": reply_key,
                "classification": result.classification,
                "derived_event_type": outcome_event_type.value if outcome_event_type else None,
                "event_ids": emitted_event_ids,
            }
        except Exception as exc:
            failed_event_id = _event_id(EventType.REPLY_TRIAGE_FAILED, reply_key)
            if not ledger.exists(failed_event_id):
                ledger.append(
                    {
                        "event_id": failed_event_id,
                        "event_type": EventType.REPLY_TRIAGE_FAILED.value,
                        "correlation_id": cid,
                        "entity_id": entity_id,
                        "payload": {
                            "reply_key": reply_key,
                            "draft_id": reply.draft_id,
                            "provider_message_id": reply.provider_message_id,
                            "received_at": received_payload["received_at"],
                            "error_type": exc.__class__.__name__.lower(),
                            "error_message": str(exc)[:160],
                        },
                    }
                )
            raise
