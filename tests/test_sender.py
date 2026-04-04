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


def _append_draft(entity_id: str, draft_id: str = "draft-1") -> None:
    ledger.append(
        {
            "event_id": draft_id,
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "entity_id": entity_id,
                "segment": "industrial_distributor",
                "subject": "Film-faced eucalyptus panel supply program",
                "body": "Body here",
                "template_version": "v2_merge_fields",
                "generation_mode": "deterministic",
                "to_hint": "buyer@example.com",
            },
        }
    )


def test_sender_emits_sent_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "OUTBOUND_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OUTBOUND_DRY_RUN", True)

    _append_draft("entity-1", draft_id="draft-1")
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
    requested = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value]
    accepted = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]
    blocked = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    assert len(requested) == 1
    assert len(accepted) == 1
    assert len(sent) == 1
    assert len(blocked) == 1
    assert sent[0]["payload"]["draft_id"] == "draft-1"
    assert sent[0]["payload"]["provider_name"] == "mock"
    assert accepted[0]["payload"]["provider_message_id"].startswith("mock-")


def test_sender_records_provider_failure_without_sent_event(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "OUTBOUND_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OUTBOUND_DRY_RUN", False)
    monkeypatch.setattr(settings, "OUTBOUND_PROVIDER_API_KEY", "fail")

    _append_draft("entity-fail", draft_id="draft-fail")
    _append_outbox_ready("entity-fail", draft_id="draft-fail")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["failed"] == 1

    events = list(ledger.read())
    requested = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value]
    failed = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_FAILED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]

    assert len(requested) == 1
    assert len(failed) == 1
    assert failed[0]["payload"]["provider_name"] == "mock"
    assert failed[0]["payload"]["failure_reason"] == "provider_rejected_request"
    assert sent == []


def test_sender_blocks_manual_review_entities(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "OUTBOUND_PROVIDER", "mock")

    _append_qualification("entity-manual", risk_score=1, requires_manual_review=True)
    _append_draft("entity-manual", draft_id="draft-manual")
    _append_outbox_ready("entity-manual", draft_id="draft-manual")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    events = list(ledger.read())
    blocked = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    requested = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]

    assert len(blocked) == 1
    assert requested == []
    assert blocked[0]["payload"]["blocked_reasons"] == ["requires_manual_review"]
    assert sent == []


def test_sender_blocks_when_risk_exceeds_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "SEND_POLICY_RISK_THRESHOLD", 3)

    _append_qualification("entity-risk", risk_score=4, requires_manual_review=False)
    _append_draft("entity-risk", draft_id="draft-risk")
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
    _append_draft("entity-suppressed", draft_id="draft-suppressed")
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

    _append_draft("entity-sent", draft_id="draft-sent")
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
    requested = [e for e in events if e.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value]
    sent = [e for e in events if e.get("event_type") == EventType.OUTBOUND_SENT.value]

    assert len(blocked) == 1
    assert requested == []
    assert blocked[0]["payload"]["blocked_reasons"] == ["already_sent"]
    assert len(sent) == 1


def test_sender_blocks_unsubscribed_entities_from_future_outreach(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    _append_candidate("entity-unsubscribed", "https://acme-panels.example")
    ledger.append(
        {
            "event_id": "entity-unsubscribed-unsubscribe",
            "event_type": EventType.UNSUBSCRIBE_RECORDED.value,
            "correlation_id": "c1",
            "entity_id": "entity-unsubscribed",
            "payload": {
                "reply_key": "reply-1",
                "received_at": "2026-04-04T09:00:00+00:00",
                "reply_text_snippet": "unsubscribe",
                "classification": "unsubscribe",
                "matched_phrase": "unsubscribe",
            },
        }
    )
    _append_draft("entity-unsubscribed", draft_id="draft-unsubscribed")
    _append_outbox_ready("entity-unsubscribed", draft_id="draft-unsubscribed")

    result = run_once(limit=10)

    assert result["emitted"] == 0
    assert result["blocked"] == 1

    blocked = [e for e in ledger.read() if e.get("event_type") == EventType.OUTBOUND_SEND_BLOCKED.value]
    assert len(blocked) == 1
    assert blocked[0]["payload"]["blocked_reasons"] == ["marketing_suppressed:unsubscribe"]
