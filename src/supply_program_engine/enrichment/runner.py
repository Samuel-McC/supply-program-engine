from __future__ import annotations

from requests import RequestException

from supply_program_engine import ledger
from supply_program_engine.enrichment.fetch import fetch_public_website
from supply_program_engine.enrichment.signals import SIGNAL_VERSION, derive_signals
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import Candidate, EventType
from supply_program_engine.observability import trace_span

log = get_logger("supply_program_engine")


def _event_id(event_type: EventType, candidate_payload: dict) -> str:
    return ledger.generate_event_id(
        {
            "event_type": event_type.value,
            "candidate": candidate_payload,
            "signal_version": SIGNAL_VERSION,
        }
    )


def run_once(limit: int = 50) -> dict:
    processed = 0
    started = 0
    completed = 0
    failed = 0
    skipped_duplicates = 0

    with trace_span("runner.enrichment.batch", task_type="enrichment_run", extra={"limit": limit}):
        for rec in ledger.read():
            if processed >= limit:
                break

            if rec.get("event_type") != EventType.CANDIDATE_INGESTED.value:
                continue

            candidate_payload = rec.get("payload") or {}
            entity_id = rec.get("entity_id") or "unknown"
            cid = rec.get("correlation_id") or generate_correlation_id()

            completed_event_id = _event_id(EventType.ENRICHMENT_COMPLETED, candidate_payload)
            failed_event_id = _event_id(EventType.ENRICHMENT_FAILED, candidate_payload)

            processed += 1

            with trace_span(
                "runner.enrichment.entity",
                correlation_id=cid,
                entity_id=entity_id,
                event_type=EventType.ENRICHMENT_COMPLETED.value,
            ):
                if ledger.exists(completed_event_id) or ledger.exists(failed_event_id):
                    skipped_duplicates += 1
                    continue

                started_event_id = _event_id(EventType.ENRICHMENT_STARTED, candidate_payload)
                if not ledger.exists(started_event_id):
                    candidate = Candidate(**candidate_payload)
                    ledger.append(
                        {
                            "event_id": started_event_id,
                            "event_type": EventType.ENRICHMENT_STARTED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "website_present": bool(candidate.website),
                                "signal_version": SIGNAL_VERSION,
                                "source": "website_fetch" if candidate.website else "heuristic_only",
                            },
                        }
                    )
                    started += 1

                candidate = Candidate(**candidate_payload)

                try:
                    fetched = fetch_public_website(candidate.website) if candidate.website else None
                    payload = derive_signals(
                        company_name=candidate.company_name,
                        discovered_via=candidate.discovered_via,
                        source=candidate.source,
                        website=candidate.website,
                        fetched=fetched,
                    )
                    ledger.append(
                        {
                            "event_id": completed_event_id,
                            "event_type": EventType.ENRICHMENT_COMPLETED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": payload,
                        }
                    )
                    completed += 1
                    log.info(
                        "enrichment_completed",
                        extra={"correlation_id": cid, "entity_id": entity_id, "event_id": completed_event_id},
                    )
                except RequestException as exc:
                    ledger.append(
                        {
                            "event_id": failed_event_id,
                            "event_type": EventType.ENRICHMENT_FAILED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "website_present": bool(candidate.website),
                                "domain": derive_signals(
                                    company_name=candidate.company_name,
                                    discovered_via=candidate.discovered_via,
                                    source=candidate.source,
                                    website=candidate.website,
                                )["domain"],
                                "signal_version": SIGNAL_VERSION,
                                "source": "website_fetch",
                                "error_type": exc.__class__.__name__.lower(),
                                "error_message": str(exc)[:160],
                            },
                        }
                    )
                    failed += 1
                    log.warning(
                        "enrichment_failed",
                        extra={
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "error_type": exc.__class__.__name__.lower(),
                        },
                    )

    return {
        "processed": processed,
        "started": started,
        "completed": completed,
        "failed": failed,
        "skipped_duplicates": skipped_duplicates,
    }
