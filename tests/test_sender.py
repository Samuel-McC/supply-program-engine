from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.models import EventType
from supply_program_engine.outbound.sender import run_once


def _append_qualification(
    entity_id: str,
    *,
    risk_score: int = 0,
    requires_manual_review: bool = False,
) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-qualification",
            "event_type": EventType.QUALIFICATION_COMPUTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "segment": "industrial_distributor",
                "priority_score": 10,
                "estimated_containers_per_month": 30,
                "decision_maker_type": "Procurement",
                "scoring_version": "v2_policy_engine",
                "risk_score": risk_score,
                "requires_manual_review": requires_manual_review,
                "policy_version": "v1",
                "compliance_findings": [],
            },
        }
    )


def _append_candidate(entity_id: str, website: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-candidate",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Acme Panels",
                "website": website,
                "location": "TX",
                "source": "manual",
                "discovered_via": "industrial distributor",
            },
        }
    )


def _append_outbox_ready(entity_id: str, draft_id: str = "draft-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-outbox",
            "event_type": EventType.OUTBOX_READY.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "channel": "email",
                "status": "ready",
            },
        }
    )


def test_sender_emits_sent_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_outbox_ready("entity-1")

    r1 = run_once(limit=10)
    assert r1["emitted"] == 1

    r2 = run_once(limit=10)
    assert r2["emitted"] == 0
    assert r2["blocked"] == 1

    r3 = run_once(limit=10)
    assert r3["emitted"] == 0
    assert r3["skipped_duplicates"] == 1

    events = list(ledger.read())
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]
    blocked = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    assert len(sent) == 1
    assert len(blocked) == 1
    assert sent[0]["payload"]["draft_id"] == "draft-1"


def test_sender_blocks_manual_review_entities(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_qualification("entity-manual", risk_score=1, requires_manual_review=True)
    _append_outbox_ready("entity-manual", draft_id="draft-manual")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    events = list(ledger.read())
    blocked = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]

    assert len(blocked) == 1
    assert blocked[0]["payload"]["blocked_reasons"] == ["requires_manual_review"]
    assert sent == []


def test_sender_blocks_when_risk_exceeds_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "SEND_POLICY_RISK_THRESHOLD", 3)

    _append_qualification("entity-risk", risk_score=4, requires_manual_review=False)
    _append_outbox_ready("entity-risk", draft_id="draft-risk")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    blocked = [e for e in ledger.read() if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    assert len(blocked) == 1
    assert blocked[0]["payload"]["blocked_reasons"] == ["risk_score_above_threshold:4>3"]


def test_sender_blocks_suppressed_domains(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "SUPPRESSED_DOMAINS", "blocked.example")

    _append_candidate("entity-suppressed", "https://blocked.example")
    _append_outbox_ready("entity-suppressed", draft_id="draft-suppressed")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    blocked = [e for e in ledger.read() if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    assert len(blocked) == 1
    assert blocked[0]["payload"]["blocked_reasons"] == ["domain_suppressed:blocked.example"]


def test_sender_blocks_already_sent_entities_without_resending(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_outbox_ready("entity-sent", draft_id="draft-sent")
    ledger.append(
        {
            "event_id": "entity-sent-sent",
            "event_type": EventType.OUTBOUND_SENT.value,
            "correlation_id": "c1",
            "entity_id": "entity-sent",
            "payload": {
                "draft_id": "draft-sent",
                "channel": "email",
                "status": "sent",
            },
        }
    )

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    events = list(ledger.read())
    blocked = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]

    assert len(blocked) == 1
    assert blocked[0]["payload"]["blocked_reasons"] == ["already_sent"]
    assert len(sent) == 1
