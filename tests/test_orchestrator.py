from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.orchestrator import run_once


def test_orchestrator_emits_qualification_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "ing-1",
            "event_type": "candidate_ingested",
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "company_name": "Acme Formwork",
                "website": "https://acmeformwork.com",
                "location": "TX",
                "source": "manual",
                "discovered_via": "formwork contractor",
            },
        }
    )

    r1 = run_once(limit=10)
    assert r1["emitted"] == 1

    r2 = run_once(limit=10)
    assert r2["emitted"] == 0
    assert r2["skipped_duplicates"] == 1


def test_orchestrator_qualifies_distributor_with_policy_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "ing-1",
            "event_type": "candidate_ingested",
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "company_name": "Globex Lumber Distributor",
                "website": "https://globexlumber.com",
                "location": "CA",
                "source": "manual",
                "discovered_via": "industrial lumber distributor",
            },
        }
    )

    run_once(limit=10)

    events = list(ledger.read())
    quals = [e for e in events if e.get("event_type") == "qualification_computed"]
    assert len(quals) == 1
    assert quals[0]["payload"]["segment"] == "industrial_distributor"
    assert quals[0]["payload"]["priority_score"] == 10
    assert quals[0]["payload"]["estimated_containers_per_month"] == 30
    assert quals[0]["payload"]["scoring_version"] == "v2_policy_engine"
    assert quals[0]["payload"]["risk_score"] == 0
    assert quals[0]["payload"]["requires_manual_review"] is False
    assert len(quals[0]["payload"]["compliance_findings"]) >= 1


def test_orchestrator_unknown_goes_manual_review_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "ing-1",
            "event_type": "candidate_ingested",
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "company_name": "Mystery Co",
                "website": "",
                "location": "NV",
                "source": "manual",
                "discovered_via": "unknown",
            },
        }
    )

    run_once(limit=10)

    events = list(ledger.read())
    quals = [e for e in events if e.get("event_type") == "qualification_computed"]
    assert len(quals) == 1
    assert quals[0]["payload"]["segment"] == "unknown"
    assert quals[0]["payload"]["priority_score"] == 3
    assert quals[0]["payload"]["scoring_version"] == "v2_policy_engine"
    assert quals[0]["payload"]["requires_manual_review"] is True
    assert quals[0]["payload"]["risk_score"] >= 1


def test_orchestrator_uses_enrichment_evidence_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "ing-1",
            "event_type": "candidate_ingested",
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "company_name": "Acme Supply",
                "website": "https://acmesupply.com",
                "location": "TX",
                "source": "manual",
                "discovered_via": "unknown",
            },
        }
    )
    ledger.append(
        {
            "event_id": "enrich-1",
            "event_type": "enrichment_completed",
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "signal_version": "enrichment_v1",
                "source": "website_fetch",
                "domain": "acmesupply.com",
                "website_present": True,
                "fetch_succeeded": True,
                "website_title": "Acme Industrial Distributor",
                "meta_description": "Commercial distributor and contractor supply partner",
                "contact_page_detected": True,
                "construction_keywords_found": False,
                "distributor_keywords_found": True,
                "likely_b2b": True,
                "matched_keywords": ["contractor", "distributor"],
            },
        }
    )

    run_once(limit=10)

    events = list(ledger.read())
    quals = [e for e in events if e.get("event_type") == "qualification_computed"]
    assert len(quals) == 1
    assert quals[0]["payload"]["segment"] == "industrial_distributor"
    assert "enrichment_distributor_keywords_found" in quals[0]["payload"]["evidence"]
