from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.data_controls.models import (
    SubjectRequestRecord,
    SubjectRequestStatusUpdate,
    SuppressionRecord,
    iso_now,
    normalize_target_value,
)
from supply_program_engine.data_controls.suppression import record_suppression
from supply_program_engine.models import EventType, PipelineEntityView


def create_subject_request(request: SubjectRequestRecord, correlation_id: str) -> dict[str, object]:
    target_value = normalize_target_value(request.target_type, request.target_value)
    request_id = request.request_id or ledger.generate_event_id(
        {
            "request_type": request.request_type,
            "target_type": request.target_type,
            "target_value": target_value,
            "source": request.source,
            "notes": request.notes,
        }
    )
    payload = {
        "request_id": request_id,
        "request_type": request.request_type,
        "target_type": request.target_type,
        "target_value": target_value,
        "status": request.status,
        "requested_at": request.requested_at or iso_now(),
        "entity_id": request.entity_id,
        "actor": request.actor,
        "source": request.source,
        "notes": request.notes,
    }
    event_id = ledger.generate_event_id(
        {
            "event_type": EventType.SUBJECT_REQUEST_RECORDED.value,
            "request_id": request_id,
            "status": request.status,
            "target_type": request.target_type,
            "target_value": target_value,
        }
    )
    if ledger.exists(event_id):
        return {"status": "duplicate", "request_id": request_id, "event_id": event_id}

    stored = ledger.append(
        {
            "event_id": event_id,
            "event_type": EventType.SUBJECT_REQUEST_RECORDED.value,
            "correlation_id": correlation_id,
            "entity_id": request.entity_id,
            "payload": payload,
        }
    )
    return {"status": "recorded", "request_id": request_id, "event_id": stored["event_id"], "payload": payload}


def subject_request_states() -> dict[str, dict]:
    requests: dict[str, dict] = {}
    for rec in ledger.read():
        event_type = rec.get("event_type")
        payload = rec.get("payload") or {}
        if event_type == EventType.SUBJECT_REQUEST_RECORDED.value:
            request_id = payload.get("request_id")
            if not request_id:
                continue
            requests[request_id] = dict(payload)
        elif event_type == EventType.SUBJECT_REQUEST_STATUS_UPDATED.value:
            request_id = payload.get("request_id")
            if not request_id or request_id not in requests:
                continue
            requests[request_id]["status"] = payload.get("status", requests[request_id].get("status"))
            requests[request_id]["updated_at"] = payload.get("updated_at")
            requests[request_id]["updated_by"] = payload.get("actor")
            if payload.get("notes"):
                requests[request_id]["notes"] = payload.get("notes")
    return requests


def subject_requests_for_entity(entity: PipelineEntityView) -> list[dict]:
    domain = normalize_target_value("domain", entity.website) if entity.website else None
    email = normalize_target_value("email", entity.draft_to_hint) if entity.draft_to_hint else None
    matched: list[dict] = []
    seen: set[str] = set()
    for request in subject_request_states().values():
        target_type = request.get("target_type")
        target_value = request.get("target_value")
        match = False
        if request.get("entity_id") == entity.entity_id:
            match = True
        elif target_type == "entity" and target_value == entity.entity_id:
            match = True
        elif target_type == "domain" and domain and target_value == domain:
            match = True
        elif target_type == "email" and email and target_value == email:
            match = True

        request_id = str(request.get("request_id"))
        if match and request_id not in seen:
            seen.add(request_id)
            matched.append(request)
    return sorted(matched, key=lambda request: request.get("updated_at") or request.get("requested_at") or "")


def update_subject_request_status(update: SubjectRequestStatusUpdate, correlation_id: str) -> dict[str, object]:
    requests = subject_request_states()
    request = requests.get(update.request_id)
    if request is None:
        raise ValueError("subject_request_not_found")

    payload = {
        "request_id": update.request_id,
        "status": update.status,
        "updated_at": update.updated_at or iso_now(),
        "actor": update.actor,
        "notes": update.notes,
    }
    event_id = ledger.generate_event_id(
        {
            "event_type": EventType.SUBJECT_REQUEST_STATUS_UPDATED.value,
            "request_id": update.request_id,
            "status": update.status,
            "notes": update.notes,
        }
    )
    if ledger.exists(event_id):
        return {"status": "duplicate", "request_id": update.request_id, "event_id": event_id}

    stored = ledger.append(
        {
            "event_id": event_id,
            "event_type": EventType.SUBJECT_REQUEST_STATUS_UPDATED.value,
            "correlation_id": correlation_id,
            "entity_id": request.get("entity_id"),
            "payload": payload,
        }
    )

    suppression_result = None
    if request.get("request_type") == "objection_to_marketing" and update.status in {"approved", "completed"}:
        suppression_result = record_suppression(
            SuppressionRecord(
                target_type=request["target_type"],
                target_value=request["target_value"],
                reason="objection_to_marketing",
                actor=update.actor,
                source="subject_request",
                notes=update.notes or request.get("notes"),
                entity_id=request.get("entity_id"),
            ),
            correlation_id=correlation_id,
        )

    return {
        "status": "updated",
        "request_id": update.request_id,
        "event_id": stored["event_id"],
        "payload": payload,
        "suppression": suppression_result,
    }
