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


def test_orchestrator_qualifies_distributor(tmp_path, monkeypatch):
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
    assert quals[0]["payload"]["scoring_version"] == "v1"
    assert len(quals[0]["payload"]["evidence"]) >= 1