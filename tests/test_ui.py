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


def test_entity_detail_shows_enrichment_section(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()
    ledger.append(
        {
            "event_id": "entity-1-enrichment",
            "event_type": EventType.ENRICHMENT_COMPLETED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "signal_version": "enrichment_v1",
                "source": "website_fetch",
                "domain": "lonestarpanels-example.com",
                "website_present": True,
                "fetch_succeeded": True,
                "website_title": "Lone Star Industrial Panels",
                "meta_description": "Commercial distributor and contractor supply partner",
                "contact_page_detected": True,
                "construction_keywords_found": True,
                "distributor_keywords_found": True,
                "likely_b2b": True,
                "matched_keywords": ["construction", "distributor"],
            },
        }
    )

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Enrichment" in response.text
    assert "Lone Star Industrial Panels" in response.text
    assert "contact_page_detected: yes" in response.text


def test_entity_detail_shows_provider_send_information(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()
    ledger.append(
        {
            "event_id": "entity-1-provider-requested",
            "event_type": EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "draft_id": "draft-1",
                "provider_name": "mock",
                "requested_at": "2026-04-01T12:00:00+00:00",
                "status": "requested",
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-provider-accepted",
            "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "draft_id": "draft-1",
                "provider_name": "mock",
                "provider_message_id": "mock-123",
                "accepted_at": "2026-04-01T12:00:01+00:00",
                "status": "accepted",
            },
        }
    )

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Provider Send" in response.text
    assert "mock-123" in response.text
    assert "accepted" in response.text


def test_entity_detail_shows_reply_triage_section(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()
    ledger.append(
        {
            "event_id": "entity-1-reply-received",
            "event_type": EventType.REPLY_RECEIVED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "reply_key": "reply-1",
                "received_at": "2026-04-01T12:10:00+00:00",
                "reply_text": "Please unsubscribe me from future emails.",
                "reply_text_snippet": "Please unsubscribe me from future emails.",
                "metadata": {},
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-reply-classified",
            "event_type": EventType.REPLY_CLASSIFIED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "reply_key": "reply-1",
                "received_at": "2026-04-01T12:10:00+00:00",
                "reply_text_snippet": "Please unsubscribe me from future emails.",
                "classification": "unsubscribe",
                "matched_phrase": "unsubscribe",
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-unsubscribe",
            "event_type": EventType.UNSUBSCRIBE_RECORDED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "reply_key": "reply-1",
                "received_at": "2026-04-01T12:10:00+00:00",
                "reply_text_snippet": "Please unsubscribe me from future emails.",
                "classification": "unsubscribe",
                "matched_phrase": "unsubscribe",
            },
        }
    )

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Reply Triage" in response.text
    assert "unsubscribe" in response.text
    assert "unsubscribe_recorded: yes" in response.text


def test_entity_detail_shows_learning_outcome_section(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)
    _seed_candidate()
    ledger.append(
        {
            "event_id": "entity-1-learning-outcome",
            "event_type": EventType.OUTCOME_RECORDED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "outcome_version": "learning_v1",
                "outcome_category": "reply_interested",
                "source": "mock_directory",
                "segment": "industrial_distributor",
                "template_version": "v1",
                "reply_classification": "interested",
                "basis": {
                    "sent_at": "2026-04-02T09:00:00+00:00",
                    "last_reply_received_at": "2026-04-02T09:10:00+00:00",
                },
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-learning-feedback",
            "event_type": EventType.SCORING_FEEDBACK_GENERATED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "outcome_version": "learning_v1",
                "outcome_category": "reply_interested",
                "source": "mock_directory",
                "segment": "industrial_distributor",
                "template_version": "v1",
                "reply_classification": "interested",
                "source_quality": "strong",
                "template_effectiveness": "positive",
                "reply_signal_strength": "high",
                "counts": {"observations": 1, "positive": 1, "negative": 0},
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-source-performance",
            "event_type": EventType.SOURCE_PERFORMANCE_UPDATED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "outcome_version": "learning_v1",
                "outcome_category": "reply_interested",
                "source": "mock_directory",
                "segment": "industrial_distributor",
                "template_version": "v1",
                "reply_classification": "interested",
                "source_quality": "strong",
                "template_effectiveness": "positive",
                "reply_signal_strength": "high",
                "counts": {"observations": 1, "positive": 1, "negative": 0},
                "performance_note": "mock_directory / industrial_distributor: strong (reply_interested)",
            },
        }
    )
    ledger.append(
        {
            "event_id": "entity-1-template-performance",
            "event_type": EventType.TEMPLATE_PERFORMANCE_UPDATED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "outcome_version": "learning_v1",
                "outcome_category": "reply_interested",
                "source": "mock_directory",
                "segment": "industrial_distributor",
                "template_version": "v1",
                "reply_classification": "interested",
                "source_quality": "strong",
                "template_effectiveness": "positive",
                "reply_signal_strength": "high",
                "counts": {"observations": 1, "positive": 1, "negative": 0},
                "performance_note": "v1: positive (reply_interested)",
            },
        }
    )

    response = client.get("/ui/entity/entity-1")

    assert response.status_code == 200
    assert "Learning / Outcome" in response.text
    assert "reply_interested" in response.text
    assert "strong" in response.text
    assert "positive" in response.text
