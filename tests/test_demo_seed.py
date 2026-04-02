from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.demo_seed import run_demo_seed
from supply_program_engine.models import EventType


def test_demo_seed_populates_end_to_end_demo_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    summary = run_demo_seed()
    entities = {entity["company_name"]: entity for entity in summary["entities"]}

    assert summary["entity_count"] == 3
    assert entities["Atlas Industrial Lumber"]["status"] == "sent"
    assert entities["Atlas Industrial Lumber"]["latest_outcome"] == "reply_interested"
    assert entities["Beacon Formwork Supply"]["status"] == "sent"
    assert entities["Beacon Formwork Supply"]["latest_outcome"] == "unsubscribe"
    assert entities["Cedar Ridge Distributor"]["status"] == "send_blocked"
    assert entities["Cedar Ridge Distributor"]["blocked_reasons"] == ["requires_manual_review"]

    events = list(ledger.read())
    assert len([event for event in events if event["event_type"] == EventType.CANDIDATE_INGESTED.value]) == 3
    assert len([event for event in events if event["event_type"] == EventType.OUTBOUND_SENT.value]) == 2


def test_demo_seed_is_safe_to_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    first = run_demo_seed()
    first_event_count = len(list(ledger.read()))

    second = run_demo_seed()
    second_event_count = len(list(ledger.read()))
    entities = {entity["company_name"]: entity for entity in second["entities"]}

    assert second_event_count == first_event_count
    assert second["steps"]["sender"]["processed"] == 0
    assert entities["Atlas Industrial Lumber"]["status"] == "sent"
    assert entities["Beacon Formwork Supply"]["status"] == "sent"
    assert entities["Cedar Ridge Distributor"]["status"] == "send_blocked"
    assert first["entity_ids"] == second["entity_ids"]
