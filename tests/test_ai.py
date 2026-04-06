from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.config import settings
from supply_program_engine.models import EventType


def _client(
    tmp_path,
    monkeypatch,
    *,
    ai_enabled: bool = True,
    ai_drafts_enabled: bool = True,
    ai_provider: str = "mock",
    ai_model: str = "mock-draft-personalizer-v1",
) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setattr(settings, "AI_ENABLED", ai_enabled)
    monkeypatch.setattr(settings, "AI_DRAFTS_ENABLED", ai_drafts_enabled)
    monkeypatch.setattr(settings, "AI_PROVIDER", ai_provider)
    monkeypatch.setattr(settings, "AI_MODEL", ai_model)
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
                "source": "mock_directory",
                "discovered_via": "industrial distributor",
                "source_query": "industrial distributor texas",
                "source_region": "Texas",
            },
        }
    )


def _append_draft(entity_id: str = "entity-1", draft_id: str = "draft-1") -> None:
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
                "subject": "Film-faced eucalyptus panel supply program for Acme Panels",
                "body": (
                    "Hi Acme Panels,\n\n"
                    "We support industrial_distributor buyers in TX with a structural panel supply program.\n\n"
                    "If relevant, we can share specs and pricing.\n\n"
                    "Regards,\n"
                    "Supply Program"
                ),
                "template_version": "v2_merge_fields",
                "generation_mode": "deterministic",
            },
        }
    )


def test_ai_draft_endpoint_emits_suggestion_event(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _append_candidate()
    _append_draft()

    response = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "suggested"
    assert body["entity_id"] == "entity-1"
    assert body["source_draft_id"] == "draft-1"
    assert body["provider_name"] == "mock"
    assert body["model_name"] == "mock-draft-personalizer-v1"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_SUGGESTED.value]
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["source_draft_id"] == "draft-1"
    assert payload["provider_name"] == "mock"
    assert payload["model_name"] == "mock-draft-personalizer-v1"
    assert payload["prompt_version"] == "ai_draft_personalizer_v1"
    assert payload["generated_at"]
    assert payload["suggested_subject"]
    assert payload["suggested_opening"]
    assert payload["suggested_body"]


def test_ai_draft_endpoint_emits_failure_event_when_provider_is_unavailable(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, ai_provider="unsupported")
    _append_candidate()
    _append_draft()

    response = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "unsupported_provider:unsupported"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_GENERATION_FAILED.value]
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["source_draft_id"] == "draft-1"
    assert payload["prompt_version"] == "ai_draft_personalizer_v1"
    assert payload["failure_reason"] == "unsupported_provider:unsupported"


def test_ai_draft_endpoint_is_idempotent_for_same_source_draft(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _append_candidate()
    _append_draft()

    first = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())
    second = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "suggested"
    assert second.json()["status"] == "duplicate"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_SUGGESTED.value]
    assert len(events) == 1
