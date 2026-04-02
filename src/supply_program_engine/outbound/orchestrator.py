from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.enrichment import latest_completed_enrichment
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import EventType
from supply_program_engine.observability import trace_span
from supply_program_engine.outbound.drafts import make_draft

log = get_logger("supply_program_engine")


def _draft_event_id(entity_id: str, segment: str, qualification_event_id: str) -> str:
    return ledger.generate_event_id(
        {
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "entity_id": entity_id,
            "segment": segment,
            "qualification_event_id": qualification_event_id,
        }
    )


def _candidate_payload_for_entity(entity_id: str) -> dict:
    for rec in ledger.read(entity_id=entity_id):
        if rec.get("event_type") == EventType.CANDIDATE_INGESTED.value:
            return rec.get("payload") or {}
    return {}


def run_once(limit: int = 50) -> dict:
    processed = 0
    emitted = 0
    skipped_duplicates = 0

    with trace_span("runner.outbound_draft.batch", task_type="outbound_draft_run", extra={"limit": limit}):
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
            qualification_event_id = rec.get("event_id") or "unknown"

            event_id = _draft_event_id(
                entity_id=entity_id,
                segment=segment,
                qualification_event_id=qualification_event_id,
            )

            with trace_span(
                "runner.outbound_draft.entity",
                correlation_id=cid,
                entity_id=entity_id,
                event_type=EventType.OUTBOUND_DRAFT_CREATED.value,
                extra={"segment": segment, "qualification_event_id": qualification_event_id},
            ):
                if ledger.exists(event_id):
                    skipped_duplicates += 1
                    continue

                candidate_payload = _candidate_payload_for_entity(entity_id)
                enrichment = latest_completed_enrichment(entity_id)
                company_name = candidate_payload.get("company_name", "there")
                location = candidate_payload.get("location")

                draft = make_draft(
                    draft_id=event_id,
                    entity_id=entity_id,
                    company_name=company_name,
                    location=location,
                    segment=segment,
                    enrichment_signals=(enrichment or {}).get("payload"),
                )

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
