from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.config import settings
from supply_program_engine.models import EventType


def _client_with_temp_ledger(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    return TestClient(create_app())


def _append_candidate(entity_id: str) -> None:
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


def _append_draft(entity_id: str, draft_id: str) -> None:
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
                "template_version": "v1",
                "generation_mode": "deterministic",
            },
        }
    )


def _append_provider_accepted(entity_id: str, draft_id: str, provider_message_id: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-provider-accepted",
            "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "provider_name": "mock",
                "provider_message_id": provider_message_id,
                "accepted_at": "2026-04-01T12:00:01+00:00",
                "status": "accepted",
            },
        }
    )


def test_reply_triage_ingests_interested_reply_by_entity_id(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-1")

    response = client.post(
        "/reply-triage/ingest",
        json={
            "entity_id": "entity-1",
            "reply_text": "Interested. Let's talk pricing next week.",
            "received_at": "2026-04-01T12:05:00+00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["classification"] == "interested"
    assert body["derived_event_type"] == EventType.LEAD_INTERESTED.value

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.REPLY_RECEIVED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.REPLY_CLASSIFIED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.LEAD_INTERESTED.value]) == 1


def test_reply_triage_ingests_not_interested_reply_by_draft_id(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-2")
    _append_draft("entity-2", "draft-2")

    response = client.post(
        "/reply-triage/ingest",
        json={
            "draft_id": "draft-2",
            "reply_text": "No thanks, we are not interested right now.",
            "received_at": "2026-04-01T12:06:00+00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "entity-2"
    assert body["classification"] == "not_interested"
    assert body["derived_event_type"] == EventType.LEAD_REJECTED.value

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.LEAD_REJECTED.value]) == 1


def test_reply_triage_ingests_unsubscribe_reply_by_provider_message_id(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-3")
    _append_provider_accepted("entity-3", "draft-3", "mock-123")

    response = client.post(
        "/reply-triage/ingest",
        json={
            "provider_message_id": "mock-123",
            "reply_text": "Please unsubscribe me from future emails.",
            "received_at": "2026-04-01T12:07:00+00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "entity-3"
    assert body["classification"] == "unsubscribe"
    assert body["derived_event_type"] == EventType.UNSUBSCRIBE_RECORDED.value

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.UNSUBSCRIBE_RECORDED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.SUPPRESSION_RECORDED.value]) == 1


def test_reply_triage_classifies_unknown_without_derived_event(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-4")

    response = client.post(
        "/reply-triage/ingest",
        json={
            "entity_id": "entity-4",
            "reply_text": "Thanks for the note.",
            "received_at": "2026-04-01T12:08:00+00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "unknown"
    assert body["derived_event_type"] is None

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.REPLY_CLASSIFIED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.LEAD_INTERESTED.value]) == 0
    assert len([e for e in events if e.get("event_type") == EventType.LEAD_REJECTED.value]) == 0
    assert len([e for e in events if e.get("event_type") == EventType.UNSUBSCRIBE_RECORDED.value]) == 0


def test_reply_triage_is_idempotent_for_duplicate_payloads(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _append_candidate("entity-5")

    payload = {
        "entity_id": "entity-5",
        "reply_text": "Interested. Send details.",
        "received_at": "2026-04-01T12:09:00+00:00",
    }

    first = client.post("/reply-triage/ingest", json=payload)
    second = client.post("/reply-triage/ingest", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"

    events = list(ledger.read())
    assert len([e for e in events if e.get("event_type") == EventType.REPLY_RECEIVED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.REPLY_CLASSIFIED.value]) == 1
    assert len([e for e in events if e.get("event_type") == EventType.LEAD_INTERESTED.value]) == 1
