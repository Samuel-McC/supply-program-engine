from __future__ import annotations

from collections.abc import Iterable

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
    compare_at = parse_iso(at) if at else None
    if compare_at is None:
        compare_at = parse_iso(iso_now())
    if compare_at is None:
        return True
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
        "actor_roles": record.actor_roles,
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
                "actor_roles": record.actor_roles,
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


def list_suppressions(records: Iterable[dict] | None = None) -> list[dict]:
    suppressions: list[dict] = []
    source_records = records if records is not None else ledger.read()
    for rec in source_records:
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
                "actor_roles": payload.get("actor_roles") or [],
                "source": payload.get("source"),
                "notes": payload.get("notes"),
            }
        )
    return suppressions

def active_suppressions_for_entity(
    entity: PipelineEntityView,
    *,
    suppressions: list[dict] | None = None,
    config_entities: set[str] | None = None,
    config_domains: set[str] | None = None,
) -> list[dict]:
    matched_suppressions: list[dict] = []
    seen: set[tuple[object, object, object]] = set()
    domain = normalize_target_value("domain", entity.website) if entity.website else None
    draft_email = normalize_target_value("email", entity.draft_to_hint) if entity.draft_to_hint else None

    registry_suppressions = suppressions if suppressions is not None else list_suppressions()
    for suppression in registry_suppressions:
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
            matched_suppressions.append(suppression)

    config_entities = config_entities if config_entities is not None else _parse_csv(settings.SUPPRESSED_ENTITIES)
    if entity.entity_id.lower() in config_entities or entity.company_name.lower() in config_entities:
        matched_suppressions.append(
            {
                "event_id": None,
                "target_type": "entity",
                "target_value": entity.entity_id,
                "reason": "manual_suppression",
                "created_at": None,
                "expires_at": None,
                "actor": None,
                "actor_roles": [],
                "source": "config",
                "notes": "Configured in SUPPRESSED_ENTITIES",
            }
        )

    config_domains = config_domains if config_domains is not None else _parse_csv(settings.SUPPRESSED_DOMAINS)
    if domain and domain in config_domains:
        matched_suppressions.append(
            {
                "event_id": None,
                "target_type": "domain",
                "target_value": domain,
                "reason": "manual_suppression",
                "created_at": None,
                "expires_at": None,
                "actor": None,
                "actor_roles": [],
                "source": "config",
                "notes": "Configured in SUPPRESSED_DOMAINS",
            }
        )

    return matched_suppressions
