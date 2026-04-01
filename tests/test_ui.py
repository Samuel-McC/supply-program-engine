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


def _seed_candidate(entity_id: str = "entity-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-ingested",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Lone Star Industrial Panels",
                "website": "https://lonestarpanels-example.com",
                "location": "Texas",
                "source": "mock_directory",
                "discovered_via": "industrial distributor",
                "external_id": "mock-1",
                "source_query": "industrial distributor",
                "source_region": "Texas",
                "source_confidence": 0.95,
            },
        }
    )


def test_discovery_dashboard_renders_provenance_view(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()

    response = client.get("/ui/discovery")

    assert response.status_code == 200
    assert "Discovery Dashboard" in response.text
    assert 'href="/ui/discovery"' in response.text
    assert "mock_directory" in response.text
    assert "industrial distributor" in response.text
    assert "Texas" in response.text


def test_entity_detail_separates_discovery_provenance_card(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Discovery Provenance" in response.text
    assert "Source Query" in response.text
    assert "External Source ID" in response.text
    assert "Operator Actions" in response.text


def test_entity_detail_shows_policy_block_reason(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)

    ledger.append(
        {
            "event_id": "entity-1-qualified",
            "event_type": EventType.QUALIFICATION_COMPUTED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "segment": "unknown",
                "priority_score": 3,
                "estimated_containers_per_month": 1,
                "decision_maker_type": "Unknown",
                "scoring_version": "v2_policy_engine",
                "risk_score": 2,
                "requires_manual_review": True,
                "policy_version": "v1",
                "compliance_findings": ["manual review required"],
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-ready",
            "event_type": EventType.OUTBOX_READY.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "draft_id": "draft-1",
                "channel": "email",
                "status": "ready",
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-blocked",
            "event_type": EventType.OUTBOUND_SEND_BLOCKED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "draft_id": "draft-1",
                "channel": "email",
                "status": "blocked",
                "blocked_reasons": ["requires_manual_review"],
                "policy_version": "send_policy_v1",
            },
        }
    )

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Send blocked by policy gate" in response.text
    assert "requires_manual_review" in response.text
