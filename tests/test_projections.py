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
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: distributor"],
            "risk_score": 0,
            "requires_manual_review": False,
            "policy_version": "v1",
            "compliance_findings": ["no compliance issues detected"],
        },
    })

    ledger.append({
        "event_id": "enrich-1",
        "event_type": EventType.ENRICHMENT_COMPLETED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "signal_version": "enrichment_v1",
            "source": "website_fetch",
            "domain": "globex.com",
            "website_present": True,
            "fetch_succeeded": True,
            "website_title": "Globex Lumber Distributor",
            "meta_description": "Commercial distributor and contractor supply partner",
            "contact_page_detected": True,
            "construction_keywords_found": False,
            "distributor_keywords_found": True,
            "likely_b2b": True,
            "matched_keywords": ["contractor", "distributor"],
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

    ledger.append({
        "event_id": "provider-requested-1",
        "event_type": EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "draft_id": "d-1",
            "provider_name": "mock",
            "requested_at": "2026-04-01T12:00:00+00:00",
            "status": "requested",
        },
    })
    ledger.append({
        "event_id": "provider-accepted-1",
        "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "draft_id": "d-1",
            "provider_name": "mock",
            "provider_message_id": "mock-123",
            "accepted_at": "2026-04-01T12:00:01+00:00",
            "status": "accepted",
        },
    })

    state = build_pipeline_state()
    assert "e1" in state
    v = state["e1"]
    assert v.company_name.startswith("Globex")
    assert v.segment == "industrial_distributor"
    assert v.priority_score == 10
    assert v.status == "draft_created"
    assert v.scoring_version == "v2_policy_engine"
    assert v.template_version == "v1"
    assert v.risk_score == 0
    assert v.requires_manual_review is False
    assert v.enrichment_status == "completed"
    assert v.enrichment_domain == "globex.com"
    assert v.enrichment_contact_page_detected is True
    assert v.enrichment_distributor_keywords_found is True
    assert v.provider_name == "mock"
    assert v.provider_message_id == "mock-123"
    assert v.provider_status == "accepted"


def test_ranking_prefers_higher_score_and_lower_risk(tmp_path, monkeypatch):
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
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: formwork"],
            "risk_score": 2,
            "requires_manual_review": True,
            "policy_version": "v1",
            "compliance_findings": ["low confidence qualification"],
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
            "scoring_version": "v2_policy_engine",
            "evidence": ["matched keyword: distributor"],
            "risk_score": 0,
            "requires_manual_review": False,
            "policy_version": "v1",
            "compliance_findings": ["no compliance issues detected"],
        },
    })

    ranked = rank_pipeline(list(build_pipeline_state().values()))
    assert ranked[0].entity_id == "e2"


def test_projection_tracks_reply_triage_state(tmp_path, monkeypatch):
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
        "event_id": "reply-received-1",
        "event_type": EventType.REPLY_RECEIVED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "reply_key": "reply-1",
            "received_at": "2026-04-01T12:10:00+00:00",
            "reply_text": "Please unsubscribe me from future emails.",
            "reply_text_snippet": "Please unsubscribe me from future emails.",
            "metadata": {},
        },
    })
    ledger.append({
        "event_id": "reply-classified-1",
        "event_type": EventType.REPLY_CLASSIFIED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "reply_key": "reply-1",
            "received_at": "2026-04-01T12:10:00+00:00",
            "reply_text_snippet": "Please unsubscribe me from future emails.",
            "classification": "unsubscribe",
            "matched_phrase": "unsubscribe",
        },
    })
    ledger.append({
        "event_id": "reply-unsubscribe-1",
        "event_type": EventType.UNSUBSCRIBE_RECORDED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "reply_key": "reply-1",
            "received_at": "2026-04-01T12:10:00+00:00",
            "reply_text_snippet": "Please unsubscribe me from future emails.",
            "classification": "unsubscribe",
            "matched_phrase": "unsubscribe",
        },
    })

    state = build_pipeline_state()
    v = state["e1"]
    assert v.reply_triage_status == "classified"
    assert v.last_reply_classification == "unsubscribe"
    assert v.last_reply_received_at == "2026-04-01T12:10:00+00:00"
    assert v.unsubscribe_recorded is True
    assert v.marketing_suppressed is True
    assert v.marketing_suppression_reason == "unsubscribe"


def test_projection_tracks_data_control_overlays(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    ledger.append({
        "event_id": "candidate-1",
        "event_type": EventType.CANDIDATE_INGESTED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "company_name": "Acme Panels",
            "website": "https://acme-panels.example",
            "location": "TX",
            "source": "manual",
            "discovered_via": "industrial distributor",
        },
    })
    ledger.append({
        "event_id": "draft-1",
        "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "draft_id": "draft-1",
            "entity_id": "e-controls",
            "segment": "industrial_distributor",
            "subject": "Supply program",
            "body": "Hello",
            "to_hint": "buyer@example.com",
            "template_version": "v1",
            "generation_mode": "deterministic",
        },
    })
    ledger.append({
        "event_id": "reply-1",
        "event_type": EventType.REPLY_RECEIVED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "reply_key": "reply-controls",
            "received_at": "2026-04-01T12:10:00+00:00",
            "reply_text": "Delete this message please.",
            "reply_text_snippet": "Delete this message please.",
            "metadata": {},
        },
    })
    ledger.append({
        "event_id": "subject-request",
        "event_type": EventType.SUBJECT_REQUEST_RECORDED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "request_id": "sr-1",
            "request_type": "erasure",
            "target_type": "entity",
            "target_value": "e-controls",
            "status": "approved",
            "requested_at": "2026-04-02T09:00:00+00:00",
            "entity_id": "e-controls",
            "actor": "privacy@example.internal",
            "source": "internal_admin",
            "notes": "Erasure request.",
        },
    })
    ledger.append({
        "event_id": "suppression-1",
        "event_type": EventType.SUPPRESSION_RECORDED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "target_type": "entity",
            "target_value": "e-controls",
            "reason": "manual_suppression",
            "created_at": "2026-04-02T09:05:00+00:00",
            "expires_at": None,
            "actor": "ops@example.internal",
            "source": "internal_admin",
            "notes": "Do not contact.",
        },
    })
    ledger.append({
        "event_id": "retention-review-1",
        "event_type": EventType.RETENTION_REVIEWED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "reply_key": "reply-controls",
            "target_event_id": "reply-1",
            "reviewed_at": "2026-04-03T10:00:00+00:00",
            "policy_name": "reply_text_retention_v1",
            "action": "redacted",
            "reason": "subject_request_erasure",
            "subject_request_id": "sr-1",
        },
    })
    ledger.append({
        "event_id": "redaction-1",
        "event_type": EventType.DATA_REDACTION_APPLIED.value,
        "correlation_id": "c1",
        "entity_id": "e-controls",
        "payload": {
            "reply_key": "reply-controls",
            "entity_id": "e-controls",
            "target_event_id": "reply-1",
            "fields_redacted": ["reply_text", "reply_text_snippet"],
            "replacement_text": "[redacted]",
            "reason": "subject_request_erasure",
            "source": "retention_runner",
            "applied_at": "2026-04-03T10:00:01+00:00",
            "actor": "privacy@example.internal",
            "subject_request_id": "sr-1",
        },
    })

    state = build_pipeline_state()
    v = state["e-controls"]
    assert v.reply_text_redacted is True
    assert v.last_reply_text_snippet == "[redacted]"
    assert v.retention_status == "redacted"
    assert "subject_request_erasure" in v.retention_notes
    assert v.latest_subject_request_type == "erasure"
    assert v.latest_subject_request_status == "approved"
    assert v.marketing_suppressed is True
    assert v.active_suppressions[0]["reason"] == "manual_suppression"


def test_projection_tracks_learning_feedback_state(tmp_path, monkeypatch):
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
        "event_id": "learning-outcome-1",
        "event_type": EventType.OUTCOME_RECORDED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "outcome_version": "learning_v1",
            "outcome_category": "reply_interested",
            "source": "manual",
            "segment": "industrial_distributor",
            "template_version": "v1",
            "reply_classification": "interested",
            "basis": {
                "sent_at": "2026-04-02T09:00:00+00:00",
                "last_reply_received_at": "2026-04-02T09:10:00+00:00",
            },
        },
    })
    ledger.append({
        "event_id": "learning-feedback-1",
        "event_type": EventType.SCORING_FEEDBACK_GENERATED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "outcome_version": "learning_v1",
            "outcome_category": "reply_interested",
            "source": "manual",
            "segment": "industrial_distributor",
            "template_version": "v1",
            "reply_classification": "interested",
            "source_quality": "strong",
            "template_effectiveness": "positive",
            "reply_signal_strength": "high",
            "counts": {"observations": 1, "positive": 1, "negative": 0},
        },
    })
    ledger.append({
        "event_id": "learning-source-1",
        "event_type": EventType.SOURCE_PERFORMANCE_UPDATED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "outcome_version": "learning_v1",
            "outcome_category": "reply_interested",
            "source": "manual",
            "segment": "industrial_distributor",
            "template_version": "v1",
            "reply_classification": "interested",
            "source_quality": "strong",
            "template_effectiveness": "positive",
            "reply_signal_strength": "high",
            "counts": {"observations": 1, "positive": 1, "negative": 0},
            "performance_note": "manual / industrial_distributor: strong (reply_interested)",
        },
    })
    ledger.append({
        "event_id": "learning-template-1",
        "event_type": EventType.TEMPLATE_PERFORMANCE_UPDATED.value,
        "correlation_id": "c1",
        "entity_id": "e1",
        "payload": {
            "outcome_version": "learning_v1",
            "outcome_category": "reply_interested",
            "source": "manual",
            "segment": "industrial_distributor",
            "template_version": "v1",
            "reply_classification": "interested",
            "source_quality": "strong",
            "template_effectiveness": "positive",
            "reply_signal_strength": "high",
            "counts": {"observations": 1, "positive": 1, "negative": 0},
            "performance_note": "v1: positive (reply_interested)",
        },
    })

    state = build_pipeline_state()
    v = state["e1"]
    assert v.latest_outcome == "reply_interested"
    assert v.learning_outcome_version == "learning_v1"
    assert v.learning_source_quality == "strong"
    assert v.learning_template_effectiveness == "positive"
    assert v.learning_reply_signal_strength == "high"
    assert v.learning_source_performance_note == "manual / industrial_distributor: strong (reply_interested)"
    assert v.learning_template_performance_note == "v1: positive (reply_interested)"
