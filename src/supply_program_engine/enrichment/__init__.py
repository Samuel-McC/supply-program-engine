from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.models import EventType

from .runner import run_once


def latest_enrichment_event(entity_id: str) -> dict | None:
    latest: dict | None = None
    for rec in ledger.read(entity_id=entity_id):
        if rec.get("event_type") in {
            EventType.ENRICHMENT_STARTED.value,
            EventType.ENRICHMENT_COMPLETED.value,
            EventType.ENRICHMENT_FAILED.value,
        }:
            latest = rec
    return latest


def latest_completed_enrichment(entity_id: str) -> dict | None:
    latest: dict | None = None
    for rec in ledger.read(entity_id=entity_id):
        if rec.get("event_type") == EventType.ENRICHMENT_COMPLETED.value:
            latest = rec
    return latest
