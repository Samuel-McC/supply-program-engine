from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.models import EventType
from supply_program_engine.outbound.orchestrator import run_once


def test_outbound_creates_draft_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "q-1",
            "event_type": EventType.QUALIFICATION_COMPUTED.value,
            "correlation_id": "c1",
            "entity_id": "entity-1",
            "payload": {
                "segment": "industrial_distributor",
                "priority_score": 10,
                "estimated_containers_per_month": 30,
                "decision_maker_type": "Procurement",
                "scoring_version": "v1",
                "evidence": ["matched keyword: distributor"],
            },
        }
    )

    r1 = run_once(limit=10)
    assert r1["emitted"] == 1

    r2 = run_once(limit=10)
    assert r2["emitted"] == 0
    assert r2["skipped_duplicates"] == 1

    events = list(ledger.read())
    drafts = [e for e in events if e.get("event_type") == EventType.OUTBOUND_DRAFT_CREATED.value]
    assert len(drafts) == 1
    assert "supply program" in drafts[0]["payload"]["subject"].lower()
    assert drafts[0]["payload"]["template_version"] == "v1"
    assert drafts[0]["payload"]["generation_mode"] == "deterministic"