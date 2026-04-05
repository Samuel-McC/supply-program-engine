from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.data_controls.models import SuppressionRecord, iso_now, normalize_target_value, parse_iso
from supply_program_engine.models import EventType, PipelineEntityView


def _parse_csv(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def _is_active(payload: dict, at: str | None = None) -> bool:
    expires_at = parse_iso(payload.get("expires_at"))
    if expires_at is None:
        return True
    compare_at = parse_iso(at) if at else parse_iso(iso_now())
    assert compare_at is not None
    return expires_at > compare_at


def record_suppression(record: SuppressionRecord, correlation_id: str) -> dict[str, object]:
    target_value = normalize_target_value(record.target_type, record.target_value)
    created_at = record.created_at or iso_now()
    payload = {
        "target_type": record.target_type,
        "target_value": target_value,
        "reason": record.reason,
        "created_at": created_at,
        "expires_at": record.expires_at,
        "actor": record.actor,
        "source": record.source,
        "notes": record.notes,
    }
    event_id = ledger.generate_event_id(
        {
            "event_type": EventType.SUPPRESSION_RECORDED.value,
            "payload": {
                "target_type": record.target_type,
                "target_value": target_value,
                "reason": record.reason,
                "expires_at": record.expires_at,
                "actor": record.actor,
                "source": record.source,
                "notes": record.notes,
            },
        }
    )

    if ledger.exists(event_id):
        return {"status": "duplicate", "event_id": event_id, "payload": payload}

    stored = ledger.append(
        {
            "event_id": event_id,
            "event_type": EventType.SUPPRESSION_RECORDED.value,
            "correlation_id": correlation_id,
            "entity_id": record.entity_id,
            "payload": payload,
        }
    )
    return {"status": "recorded", "event_id": stored["event_id"], "payload": payload}


def list_suppressions() -> list[dict]:
    suppressions: list[dict] = []
    for rec in ledger.read():
        if rec.get("event_type") != EventType.SUPPRESSION_RECORDED.value:
            continue
        payload = rec.get("payload") or {}
        suppressions.append(
            {
                "event_id": rec.get("event_id"),
                "entity_id": rec.get("entity_id"),
                "target_type": payload.get("target_type"),
                "target_value": payload.get("target_value"),
                "reason": payload.get("reason"),
                "created_at": payload.get("created_at"),
                "expires_at": payload.get("expires_at"),
                "actor": payload.get("actor"),
                "source": payload.get("source"),
                "notes": payload.get("notes"),
            }
        )
    return suppressions


def active_suppressions_for_entity(entity: PipelineEntityView) -> list[dict]:
    suppressions: list[dict] = []
    seen: set[tuple[object, object, object]] = set()
    domain = normalize_target_value("domain", entity.website) if entity.website else None
    draft_email = normalize_target_value("email", entity.draft_to_hint) if entity.draft_to_hint else None

    for suppression in list_suppressions():
        if not _is_active(suppression):
            continue
        target_type = suppression.get("target_type")
        target_value = suppression.get("target_value")
        match = False
        if suppression.get("entity_id") == entity.entity_id:
            match = True
        elif target_type == "entity" and target_value == entity.entity_id:
            match = True
        elif target_type == "domain" and domain and target_value == domain:
            match = True
        elif target_type == "email" and draft_email and target_value == draft_email:
            match = True

        if match:
            key = (suppression.get("event_id"), target_type, target_value)
            if key in seen:
                continue
            seen.add(key)
            suppressions.append(suppression)

    config_entities = _parse_csv(settings.SUPPRESSED_ENTITIES)
    if entity.entity_id.lower() in config_entities or entity.company_name.lower() in config_entities:
        suppressions.append(
            {
                "event_id": None,
                "target_type": "entity",
                "target_value": entity.entity_id,
                "reason": "manual_suppression",
                "created_at": None,
                "expires_at": None,
                "actor": None,
                "source": "config",
                "notes": "Configured in SUPPRESSED_ENTITIES",
            }
        )

    config_domains = _parse_csv(settings.SUPPRESSED_DOMAINS)
    if domain and domain in config_domains:
        suppressions.append(
            {
                "event_id": None,
                "target_type": "domain",
                "target_value": domain,
                "reason": "manual_suppression",
                "created_at": None,
                "expires_at": None,
                "actor": None,
                "source": "config",
                "notes": "Configured in SUPPRESSED_DOMAINS",
            }
        )

    return suppressions
