from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.learning.runner import run_once
from supply_program_engine.models import EventType


def _append_candidate(entity_id: str, source: str = "manual") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-candidate",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Acme Panels",
                "website": "https://acme-panels.example",
                "location": "TX",
                "source": source,
                "discovered_via": "industrial distributor",
            },
        }
    )


def _append_draft(entity_id: str, template_version: str = "v1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-draft",
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": f"{entity_id}-draft",
                "entity_id": entity_id,
                "segment": "industrial_distributor",
                "subject": "Supply program",
                "body": "Hello",
                "template_version": template_version,
                "generation_mode": "deterministic",
            },
        }
    )


def _append_sent(entity_id: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-sent",
            "event_type": EventType.OUTBOUND_SENT.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": f"{entity_id}-draft",
                "channel": "email",
                "status": "sent",
            },
        }
    )


def _append_reply_classification(entity_id: str, classification: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-reply-classified",
            "event_type": EventType.REPLY_CLASSIFIED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "received_at": "2026-04-02T09:00:00+00:00",
                "reply_text_snippet": "reply snippet",
                "classification": classification,
                "matched_phrase": classification,
            },
        }
    )


def _append_interested(entity_id: str) -> None:
    _append_reply_classification(entity_id, "interested")
    ledger.append(
        {
            "event_id": f"{entity_id}-lead-interested",
            "event_type": EventType.LEAD_INTERESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "classification": "interested",
            },
        }
    )


def _append_rejected(entity_id: str) -> None:
    _append_reply_classification(entity_id, "not_interested")
    ledger.append(
        {
            "event_id": f"{entity_id}-lead-rejected",
            "event_type": EventType.LEAD_REJECTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "classification": "not_interested",
            },
        }
    )


def _append_unsubscribe(entity_id: str) -> None:
    _append_reply_classification(entity_id, "unsubscribe")
    ledger.append(
        {
            "event_id": f"{entity_id}-unsubscribe",
            "event_type": EventType.UNSUBSCRIBE_RECORDED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "classification": "unsubscribe",
            },
        }
    )


def test_learning_derives_interested_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-1")
    _append_draft("entity-1", template_version="v1")
    _append_sent("entity-1")
    _append_interested("entity-1")

    result = run_once(limit=10)

    assert result["outcomes_recorded"] == 1
    events = list(ledger.read())
    outcome = [e for e in events if e.get("event_type") == EventType.OUTCOME_RECORDED.value]
    feedback = [e for e in events if e.get("event_type") == EventType.SCORING_FEEDBACK_GENERATED.value]
    assert len(outcome) == 1
    assert outcome[0]["payload"]["outcome_category"] == "reply_interested"
    assert len(feedback) == 1
    assert feedback[0]["payload"]["source_quality"] == "strong"
    assert feedback[0]["payload"]["template_effectiveness"] == "positive"


def test_learning_derives_rejected_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-2")
    _append_draft("entity-2", template_version="v2")
    _append_sent("entity-2")
    _append_rejected("entity-2")

    run_once(limit=10)

    outcome = [e for e in ledger.read() if e.get("event_type") == EventType.OUTCOME_RECORDED.value]
    assert len(outcome) == 1
    assert outcome[0]["payload"]["outcome_category"] == "reply_rejected"


def test_learning_derives_unsubscribe_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-3")
    _append_draft("entity-3", template_version="v2")
    _append_sent("entity-3")
    _append_unsubscribe("entity-3")

    run_once(limit=10)

    feedback = [e for e in ledger.read() if e.get("event_type") == EventType.SCORING_FEEDBACK_GENERATED.value]
    assert len(feedback) == 1
    assert feedback[0]["payload"]["outcome_category"] == "unsubscribe"
    assert feedback[0]["payload"]["template_effectiveness"] == "negative"


def test_learning_does_not_duplicate_same_outcome_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-4")
    _append_draft("entity-4")
    _append_sent("entity-4")
    _append_interested("entity-4")

    first = run_once(limit=10)
    second = run_once(limit=10)

    assert first["outcomes_recorded"] == 1
    assert second["outcomes_recorded"] == 0
    assert second["skipped_duplicates"] == 1

    outcomes = [e for e in ledger.read() if e.get("event_type") == EventType.OUTCOME_RECORDED.value]
    assert len(outcomes) == 1


def test_learning_derives_sent_no_reply_when_no_reply_events_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-5")
    _append_draft("entity-5")
    _append_sent("entity-5")

    run_once(limit=10)

    outcomes = [e for e in ledger.read() if e.get("event_type") == EventType.OUTCOME_RECORDED.value]
    assert len(outcomes) == 1
    assert outcomes[0]["payload"]["outcome_category"] == "sent_no_reply"
