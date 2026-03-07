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
            "scoring_version": "v1",
            "evidence": ["matched keyword: distributor"],
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

    state = build_pipeline_state()
    assert "e1" in state
    v = state["e1"]
    assert v.company_name.startswith("Globex")
    assert v.segment == "industrial_distributor"
    assert v.priority_score == 10
    assert v.status == "draft_created"
    assert v.scoring_version == "v1"
    assert v.template_version == "v1"


def test_ranking_prefers_higher_score(tmp_path, monkeypatch):
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
            "scoring_version": "v1",
            "evidence": ["matched keyword: formwork"],
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
            "scoring_version": "v1",
            "evidence": ["matched keyword: distributor"],
        },
    })

    ranked = rank_pipeline(list(build_pipeline_state().values()))
    assert ranked[0].entity_id == "e2"