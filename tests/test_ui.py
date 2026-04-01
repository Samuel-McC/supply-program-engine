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
