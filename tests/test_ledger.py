import os
from supply_program_engine import ledger
from supply_program_engine.config import settings


def test_append_and_exists(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(settings, "LEDGER_PATH", str(ledger_path))

    e = {"event_id": "1", "event_type": "candidate_ingested", "correlation_id": "c1", "entity_id": "acme", "payload": {"x": 1}}
    ledger.append(e)

    assert ledger.exists("1") is True
    assert ledger.exists("nope") is False


def test_chain_verification(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(settings, "LEDGER_PATH", str(ledger_path))

    ledger.append({"event_id": "1", "event_type": "candidate_ingested", "correlation_id": "c1", "entity_id": "acme", "payload": {"x": 1}})
    ledger.append({"event_id": "2", "event_type": "qualification_computed", "correlation_id": "c1", "entity_id": "acme", "payload": {"score": 10}})

    ok, err = ledger.verify_chain()
    assert ok is True
    assert err is None


def test_find_by_entity(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(settings, "LEDGER_PATH", str(ledger_path))

    ledger.append({"event_id": "1", "event_type": "candidate_ingested", "correlation_id": "c1", "entity_id": "acme", "payload": {"x": 1}})
    ledger.append({"event_id": "2", "event_type": "candidate_ingested", "correlation_id": "c2", "entity_id": "globex", "payload": {"x": 2}})

    events = ledger.find_by_entity("acme")
    assert len(events) == 1
    assert events[0]["entity_id"] == "acme"

def test_get_by_event_id(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(settings, "LEDGER_PATH", str(ledger_path))

    ledger.append({"event_id": "x1", "event_type": "candidate_ingested", "correlation_id": "c1", "entity_id": "e1", "payload": {"a": 1}})

    rec = ledger.get("x1")
    assert rec is not None
    assert rec["event_id"] == "x1"
    assert ledger.get("nope") is None