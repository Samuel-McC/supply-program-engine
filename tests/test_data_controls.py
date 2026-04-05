from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.config import settings
from supply_program_engine.models import EventType


def _client_with_temp_ledger(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "REPLY_TEXT_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "REDACTION_PLACEHOLDER", "[redacted]")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    return TestClient(create_app())


def _admin_headers() -> dict[str, str]:
    return {"x-admin-api-key": "test-admin-key"}


def _append_candidate(entity_id: str = "entity-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-candidate",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Acme Panels",
                "website": "https://acme-panels.example",
                "location": "TX",
                "source": "manual",
                "discovered_via": "industrial distributor",
            },
        }
    )


def _append_draft(entity_id: str, draft_id: str = "draft-1") -> None:
    ledger.append(
        {
            "event_id": draft_id,
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "entity_id": entity_id,
                "segment": "industrial_distributor",
                "subject": "Supply program",
                "body": "Hello",
                "to_hint": "buyer@example.com",
                "template_version": "v1",
                "generation_mode": "deterministic",
            },
        }
    )


def _append_reply(entity_id: str, reply_key: str = "reply-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-{reply_key}",
            "event_type": EventType.REPLY_RECEIVED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": reply_key,
                "received_at": "2026-03-01T12:10:00+00:00",
                "reply_text": "Please remove me and delete prior reply content.",
                "reply_text_snippet": "Please remove me and delete prior reply content.",
                "metadata": {},
            },
        }
    )


def test_manual_suppression_is_recorded_and_exported(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-1")

    response = client.post(
        "/data-controls/suppression",
        json={
            "target_type": "entity",
            "target_value": "entity-1",
            "reason": "manual_suppression",
            "entity_id": "entity-1",
            "actor": "ops@example.internal",
            "source": "internal_admin",
            "notes": "Operator suppression for do-not-contact review.",
        },
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"

    export = client.get("/data-controls/export/entity/entity-1", headers=_admin_headers())
    assert export.status_code == 200
    body = export.json()
    assert body["suppression_state"][0]["reason"] == "manual_suppression"
    assert body["entity"]["marketing_suppressed"] is True
    assert body["entity"]["active_suppressions"][0]["source"] == "internal_admin"


def test_subject_request_objection_status_update_creates_suppression(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-2")

    created = client.post(
        "/data-controls/subject-request",
        json={
            "request_type": "objection_to_marketing",
            "target_type": "entity",
            "target_value": "entity-2",
            "entity_id": "entity-2",
            "actor": "ops@example.internal",
            "source": "internal_admin",
            "notes": "Marketing objection received by operator.",
        },
        headers=_admin_headers(),
    )
    assert created.status_code == 200
    request_id = created.json()["request_id"]

    updated = client.post(
        "/data-controls/subject-request/status",
        json={
            "request_id": request_id,
            "status": "approved",
            "actor": "privacy@example.internal",
            "notes": "Approved after review.",
        },
        headers=_admin_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["suppression"]["status"] == "recorded"

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.SUBJECT_REQUEST_RECORDED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.SUBJECT_REQUEST_STATUS_UPDATED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.SUPPRESSION_RECORDED.value]) == 1


def test_erasure_request_and_retention_runner_redact_reply_text_in_export(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-3")
    _append_draft("entity-3", "draft-3")
    _append_reply("entity-3", "reply-3")

    created = client.post(
        "/data-controls/subject-request",
        json={
            "request_type": "erasure",
            "target_type": "entity",
            "target_value": "entity-3",
            "entity_id": "entity-3",
            "actor": "ops@example.internal",
            "source": "internal_admin",
            "notes": "Erasure request for reply content.",
        },
        headers=_admin_headers(),
    )
    request_id = created.json()["request_id"]
    approved = client.post(
        "/data-controls/subject-request/status",
        json={
            "request_id": request_id,
            "status": "approved",
            "actor": "privacy@example.internal",
            "notes": "Approved for redaction workflow.",
        },
        headers=_admin_headers(),
    )
    assert approved.status_code == 200

    retention = client.post("/data-controls/retention/run-once", headers=_admin_headers())
    assert retention.status_code == 200
    assert retention.json()["redacted"] == 1

    export = client.get("/data-controls/export/entity/entity-3", headers=_admin_headers())
    assert export.status_code == 200
    body = export.json()
    assert body["entity"]["reply_text_redacted"] is True
    assert body["redaction_state"]["retention_status"] == "redacted"
    reply_events = [event for event in body["event_summary"] if event["event_type"] == EventType.REPLY_RECEIVED.value]
    assert len(reply_events) == 1
    assert reply_events[0]["payload"]["reply_text"] == "[redacted]"
    assert reply_events[0]["payload"]["reply_text_snippet"] == "[redacted]"


def test_export_returns_projected_state_and_subject_requests(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-4")
    subject_request = client.post(
        "/data-controls/subject-request",
        json={
            "request_type": "access_export",
            "target_type": "entity",
            "target_value": "entity-4",
            "entity_id": "entity-4",
            "actor": "ops@example.internal",
            "source": "internal_admin",
        },
        headers=_admin_headers(),
    )
    assert subject_request.status_code == 200

    response = client.get("/data-controls/export/entity/entity-4", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["entity"]["entity_id"] == "entity-4"
    assert body["subject_requests"][0]["request_type"] == "access_export"
    assert isinstance(body["event_summary"], list)
    assert isinstance(body["suppression_state"], list)
