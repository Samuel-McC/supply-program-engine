from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.models import EventType
from supply_program_engine.projections import build_pipeline_state, rank_pipeline


def test_projection_builds_current_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append({
        "event_id": "ing-1",
        "event_type": EventType.CANDIDATE_INGESTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "company_name": "Globex Lumber Distributor",
            "website": "https://globex.com",
            "location": "CA",
            "source": "manual",
            "discovered_via": "industrial lumber distributor",
        },
    })

    ledger.append({
        "event_id": "q-1",
        "event_type": EventType.QUALIFICATION_COMPUTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "segment": "industrial_distributor",
            "priority_score": 10,
            "estimated_containers_per_month": 30,
            "decision_maker_type": "Procurement",
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: distributor"],
            "risk_score": 0,
            "requires_manual_review": False,
            "policy_version": "v1",
            "compliance_findings": ["no compliance issues detected"],
        },
    })

    ledger.append({
        "event_id": "enrich-1",
        "event_type": EventType.ENRICHMENT_COMPLETED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "signal_version": "enrichment_v1",
            "source": "website_fetch",
            "domain": "globex.com",
            "website_present": True,
            "fetch_succeeded": True,
            "website_title": "Globex Lumber Distributor",
            "meta_description": "Commercial distributor and contractor supply partner",
            "contact_page_detected": True,
            "construction_keywords_found": False,
            "distributor_keywords_found": True,
            "likely_b2b": True,
            "matched_keywords": ["contractor", "distributor"],
        },
    })

    ledger.append({
        "event_id": "d-1",
        "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "draft_id": "d-1",
            "entity_id": "e1",
            "segment": "industrial_distributor",
            "subject": "Film-faced eucalyptus panel supply program",
            "body": "Body here",
            "template_version": "v1",
            "generation_mode": "deterministic",
        },
    })

    ledger.append({
        "event_id": "provider-requested-1",
        "event_type": EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "draft_id": "d-1",
            "provider_name": "mock",
            "requested_at": "2026-04-01T12:00:00+00:00",
            "status": "requested",
        },
    })
    ledger.append({
        "event_id": "provider-accepted-1",
        "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "draft_id": "d-1",
            "provider_name": "mock",
            "provider_message_id": "mock-123",
            "accepted_at": "2026-04-01T12:00:01+00:00",
            "status": "accepted",
        },
    })

    state = build_pipeline_state()
    assert "e1" in state
    v = state["e1"]
    assert v.company_name.startswith("Globex")
    assert v.segment == "industrial_distributor"
    assert v.priority_score == 10
    assert v.status == "draft_created"
    assert v.scoring_version == "v2_policy_engine"
    assert v.template_version == "v1"
    assert v.risk_score == 0
    assert v.requires_manual_review is False
    assert v.enrichment_status == "completed"
    assert v.enrichment_domain == "globex.com"
    assert v.enrichment_contact_page_detected is True
    assert v.enrichment_distributor_keywords_found is True
    assert v.provider_name == "mock"
    assert v.provider_message_id == "mock-123"
    assert v.provider_status == "accepted"


def test_ranking_prefers_higher_score_and_lower_risk(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append({
        "event_id": "ing-1",
        "event_type": EventType.CANDIDATE_INGESTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "company_name": "A",
            "website": "https://a.com",
            "location": "TX",
            "source": "manual",
            "discovered_via": "formwork",
        },
    })
    ledger.append({
        "event_id": "q-1",
        "event_type": EventType.QUALIFICATION_COMPUTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "segment": "concrete_contractor_large",
            "priority_score": 7,
            "estimated_containers_per_month": 6,
            "decision_maker_type": "Ops",
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: formwork"],
            "risk_score": 2,
            "requires_manual_review": True,
            "policy_version": "v1",
            "compliance_findings": ["low confidence qualification"],
        },
    })

    ledger.append({
        "event_id": "ing-2",
        "event_type": EventType.CANDIDATE_INGESTED.value,
        "correlation_id": "c2",
        "entity_id": "e2",
        "payload": {
            "company_name": "B",
            "website": "https://b.com",
            "location": "CA",
            "source": "manual",
            "discovered_via": "distributor",
        },
    })
    ledger.append({
        "event_id": "q-2",
        "event_type": EventType.QUALIFICATION_COMPUTED.value,
        "correlation_id": "c2",
        "entity_id": "e2",
        "payload": {
            "segment": "industrial_distributor",
            "priority_score": 10,
            "estimated_containers_per_month": 30,
            "decision_maker_type": "Procurement",
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: distributor"],
            "risk_score": 0,
            "requires_manual_review": False,
            "policy_version": "v1",
            "compliance_findings": ["no compliance issues detected"],
        },
    })

    ranked = rank_pipeline(list(build_pipeline_state().values()))
    assert ranked[0].entity_id == "e2"
