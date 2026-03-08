from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.models import EventType
from supply_program_engine.outbound.sender import run_once


def test_sender_emits_sent_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append(
        {
            "event_id": "outbox-1",
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

    r1 = run_once(limit=10)
    assert r1["emitted"] == 1

    r2 = run_once(limit=10)
    assert r2["emitted"] == 0
    assert r2["skipped_duplicates"] == 1

    events = list(ledger.read())
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]
    assert len(sent) == 1
    assert sent[0]["payload"]["draft_id"] == "draft-1"