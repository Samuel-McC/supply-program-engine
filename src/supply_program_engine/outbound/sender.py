from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.logging import get_logger
from supply_program_engine.models import EventType
from supply_program_engine.policy import evaluate_send_policy
from supply_program_engine.projections import build_pipeline_state

log = get_logger("supply_program_engine")


def run_once(limit: int = 50) -> dict:
    """
    Simulated safe sender.

    Looks for outbox_ready events and emits outbound_sent once only.
    """
    processed = 0
    emitted = 0
    blocked = 0
    skipped_duplicates = 0
    skipped_unapproved = 0

    for rec in ledger.read():
        if processed >= limit:
            break

        if rec.get("event_type") != EventType.OUTBOX_READY.value:
            continue

        processed += 1

        cid = rec.get("correlation_id", "unknown")
        entity_id = rec.get("entity_id", "unknown")
        payload = rec.get("payload") or {}
        draft_id = payload.get("draft_id")

        if not draft_id:
            skipped_unapproved += 1
            continue

        entity = build_pipeline_state().get(entity_id)
        if entity is None:
            skipped_unapproved += 1
            continue

        decision = evaluate_send_policy(entity_id=entity_id, entity=entity)
        if not decision.allowed:
            blocked_event_id = ledger.generate_event_id(
                {
                    "event_type": EventType.OUTBOUND_SEND_BLOCKED.value,
                    "entity_id": entity_id,
                    "draft_id": draft_id,
                    "blocked_reasons": decision.blocked_reasons,
                    "policy_version": decision.policy_version,
                }
            )

            if ledger.exists(blocked_event_id):
                skipped_duplicates += 1
                continue

            ledger.append(
                {
                    "event_id": blocked_event_id,
                    "event_type": EventType.OUTBOUND_SEND_BLOCKED.value,
                    "correlation_id": cid,
                    "entity_id": entity_id,
                    "payload": {
                        "draft_id": draft_id,
                        "channel": payload.get("channel", "email"),
                        "status": "blocked",
                        "blocked_reasons": decision.blocked_reasons,
                        "policy_version": decision.policy_version,
                    },
                }
            )

            blocked += 1
            log.info(
                "outbound_send_blocked",
                extra={
                    "correlation_id": cid,
                    "entity_id": entity_id,
                    "draft_id": draft_id,
                    "blocked_reasons": decision.blocked_reasons,
                },
            )
            continue

        sent_event_id = ledger.generate_event_id(
            {
                "event_type": EventType.OUTBOUND_SENT.value,
                "entity_id": entity_id,
                "draft_id": draft_id,
            }
        )

        if ledger.exists(sent_event_id):
            skipped_duplicates += 1
            continue

        stored = ledger.append(
            {
                "event_id": sent_event_id,
                "event_type": EventType.OUTBOUND_SENT.value,
                "correlation_id": cid,
                "entity_id": entity_id,
                "payload": {
                    "draft_id": draft_id,
                    "channel": payload.get("channel", "email"),
                    "status": "sent",
                },
            }
        )

        emitted += 1
        log.info(
            "outbound_sent",
            extra={"correlation_id": cid, "entity_id": entity_id, "event_id": stored["event_id"]},
        )

    return {
        "processed": processed,
        "emitted": emitted,
        "blocked": blocked,
        "skipped_duplicates": skipped_duplicates,
        "skipped_unapproved": skipped_unapproved,
    }
