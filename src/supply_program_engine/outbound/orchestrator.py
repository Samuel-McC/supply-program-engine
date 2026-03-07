from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import EventType
from supply_program_engine.outbound.drafts import make_draft

log = get_logger("supply_program_engine")


def _draft_event_id(entity_id: str, segment: str) -> str:
    return ledger.generate_event_id(
        {"event_type": EventType.OUTBOUND_DRAFT_CREATED.value, "entity_id": entity_id, "segment": segment}
    )


def run_once(limit: int = 50) -> dict:
    processed = 0
    emitted = 0
    skipped_duplicates = 0

    for rec in ledger.read():
        if processed >= limit:
            break

        if rec.get("event_type") != EventType.QUALIFICATION_COMPUTED.value:
            continue

        processed += 1

        cid = rec.get("correlation_id") or generate_correlation_id()
        entity_id = rec.get("entity_id") or "unknown"
        q_payload = rec.get("payload") or {}
        segment = q_payload.get("segment", "unknown")

        event_id = _draft_event_id(entity_id=entity_id, segment=segment)

        if ledger.exists(event_id):
            skipped_duplicates += 1
            continue

        draft = make_draft(draft_id=event_id, entity_id=entity_id, segment=segment)

        ledger.append(
            {
                "event_id": event_id,
                "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
                "correlation_id": cid,
                "entity_id": entity_id,
                "payload": draft.model_dump(),
            }
        )

        emitted += 1
        log.info(
            "outbound_draft_created",
            extra={"correlation_id": cid, "entity_id": entity_id, "event_id": event_id, "segment": segment},
        )

    return {"processed": processed, "emitted": emitted, "skipped_duplicates": skipped_duplicates}