from __future__ import annotations

from typing import Dict, List

from supply_program_engine import ledger
from supply_program_engine.data_controls.redaction import redaction_overlays
from supply_program_engine.data_controls.subject_requests import subject_requests_for_entity
from supply_program_engine.data_controls.suppression import active_suppressions_for_entity
from supply_program_engine.models import EventType, PipelineEntityView


def build_pipeline_state() -> Dict[str, PipelineEntityView]:
    state: Dict[str, PipelineEntityView] = {}

    for rec in ledger.read():
        et = rec.get("event_type")
        entity_id = rec.get("entity_id")
        if not entity_id:
            continue

        payload = rec.get("payload") or {}
        ts = rec.get("ts")
        cid = rec.get("correlation_id")

        if entity_id not in state:
            state[entity_id] = PipelineEntityView(
                entity_id=entity_id,
                company_name="",
                correlation_id=cid,
                last_event_ts=ts,
            )

        view = state[entity_id]
        view.last_event_ts = ts or view.last_event_ts
        view.correlation_id = cid or view.correlation_id

        if et == EventType.CANDIDATE_INGESTED.value:
            view.company_name = payload.get("company_name", view.company_name)
            view.website = payload.get("website", view.website)
            view.location = payload.get("location", view.location)

            view.source = payload.get("source", view.source)
            view.discovered_via = payload.get("discovered_via", view.discovered_via)
            view.external_id = payload.get("external_id", view.external_id)
            view.source_query = payload.get("source_query", view.source_query)
            view.source_region = payload.get("source_region", view.source_region)
            view.source_confidence = payload.get("source_confidence", view.source_confidence)

            view.status = "candidate_ingested"

        elif et == EventType.ENRICHMENT_STARTED.value:
            view.enrichment_status = "started"
            view.enrichment_source = payload.get("source", view.enrichment_source)
            view.enrichment_version = payload.get("signal_version", view.enrichment_version)
            view.enrichment_website_present = bool(payload.get("website_present", view.enrichment_website_present))
            view.enrichment_error_type = None
            view.enrichment_error_message = None

        elif et == EventType.QUALIFICATION_COMPUTED.value:
            view.segment = payload.get("segment", view.segment)
            view.priority_score = int(payload.get("priority_score", view.priority_score) or 0)
            view.estimated_containers_per_month = int(
                payload.get("estimated_containers_per_month", view.estimated_containers_per_month) or 0
            )
            view.decision_maker_type = payload.get("decision_maker_type", view.decision_maker_type)
            view.scoring_version = payload.get("scoring_version", view.scoring_version)
            view.risk_score = int(payload.get("risk_score", view.risk_score) or 0)
            view.requires_manual_review = bool(
                payload.get("requires_manual_review", view.requires_manual_review)
            )
            view.policy_version = payload.get("policy_version", view.policy_version)
            view.compliance_findings = payload.get("compliance_findings", view.compliance_findings)
            view.status = "qualified"

        elif et == EventType.ENRICHMENT_COMPLETED.value:
            view.enrichment_status = "completed"
            view.enrichment_source = payload.get("source", view.enrichment_source)
            view.enrichment_version = payload.get("signal_version", view.enrichment_version)
            view.enrichment_domain = payload.get("domain", view.enrichment_domain)
            view.enrichment_website_present = bool(payload.get("website_present", view.enrichment_website_present))
            view.enrichment_fetch_succeeded = bool(payload.get("fetch_succeeded", view.enrichment_fetch_succeeded))
            view.enrichment_contact_page_detected = bool(
                payload.get("contact_page_detected", view.enrichment_contact_page_detected)
            )
            view.enrichment_construction_keywords_found = bool(
                payload.get("construction_keywords_found", view.enrichment_construction_keywords_found)
            )
            view.enrichment_distributor_keywords_found = bool(
                payload.get("distributor_keywords_found", view.enrichment_distributor_keywords_found)
            )
            view.enrichment_likely_b2b = bool(payload.get("likely_b2b", view.enrichment_likely_b2b))
            view.enrichment_matched_keywords = list(payload.get("matched_keywords", view.enrichment_matched_keywords))
            view.enrichment_website_title = payload.get("website_title", view.enrichment_website_title)
            view.enrichment_meta_description = payload.get("meta_description", view.enrichment_meta_description)
            view.enrichment_error_type = None
            view.enrichment_error_message = None

        elif et == EventType.ENRICHMENT_FAILED.value:
            view.enrichment_status = "failed"
            view.enrichment_source = payload.get("source", view.enrichment_source)
            view.enrichment_version = payload.get("signal_version", view.enrichment_version)
            view.enrichment_domain = payload.get("domain", view.enrichment_domain)
            view.enrichment_website_present = bool(payload.get("website_present", view.enrichment_website_present))
            view.enrichment_fetch_succeeded = False
            view.enrichment_error_type = payload.get("error_type", view.enrichment_error_type)
            view.enrichment_error_message = payload.get("error_message", view.enrichment_error_message)

        elif et == EventType.OUTBOUND_DRAFT_CREATED.value:
            view.draft_id = payload.get("draft_id", view.draft_id) or rec.get("event_id")
            view.draft_subject = payload.get("subject", view.draft_subject)
            view.draft_body = payload.get("body", view.draft_body)
            view.draft_to_hint = payload.get("to_hint", view.draft_to_hint)
            view.template_version = payload.get("template_version", view.template_version)
            view.status = "draft_created"

        elif et == EventType.AI_DRAFT_SUGGESTED.value:
            view.ai_suggestion_present = True
            view.ai_suggestion_status = "suggested"
            view.ai_source_draft_id = payload.get("source_draft_id", view.ai_source_draft_id)
            view.ai_provider_name = payload.get("provider_name", view.ai_provider_name)
            view.ai_model_name = payload.get("model_name", view.ai_model_name)
            view.ai_prompt_version = payload.get("prompt_version", view.ai_prompt_version)
            view.ai_generated_at = payload.get("generated_at", view.ai_generated_at)
            view.ai_generation_mode = payload.get("generation_mode", view.ai_generation_mode)
            view.ai_suggested_subject = payload.get("suggested_subject", view.ai_suggested_subject)
            view.ai_suggested_opening = payload.get("suggested_opening", view.ai_suggested_opening)
            view.ai_suggested_body = payload.get("suggested_body", view.ai_suggested_body)
            view.ai_failure_reason = None
            view.ai_failed_at = None

        elif et == EventType.AI_DRAFT_GENERATION_FAILED.value:
            view.ai_suggestion_present = False
            view.ai_suggestion_status = "failed"
            view.ai_source_draft_id = payload.get("source_draft_id", view.ai_source_draft_id)
            view.ai_provider_name = payload.get("provider_name", view.ai_provider_name)
            view.ai_model_name = payload.get("model_name", view.ai_model_name)
            view.ai_prompt_version = payload.get("prompt_version", view.ai_prompt_version)
            view.ai_generation_mode = payload.get("generation_mode", view.ai_generation_mode)
            view.ai_failure_reason = payload.get("failure_reason", view.ai_failure_reason)
            view.ai_failed_at = payload.get("failed_at", view.ai_failed_at)

        elif et == EventType.OUTBOUND_APPROVED.value:
            view.approved_by = payload.get("actor", view.approved_by)
            view.last_decision_reason = payload.get("reason", view.last_decision_reason)
            view.status = "approved"

        elif et == EventType.OUTBOUND_REJECTED.value:
            view.rejected_by = payload.get("actor", view.rejected_by)
            view.rejection_reason = payload.get("reason", view.rejection_reason)
            view.last_decision_reason = payload.get("reason", view.last_decision_reason)
            view.status = "rejected"

        elif et == EventType.OUTBOX_READY.value:
            view.outbox_ready = True
            view.blocked_reasons = []
            view.blocked_at = None
            view.status = "outbox_ready"

        elif et == EventType.OUTBOUND_SEND_BLOCKED.value:
            view.outbox_ready = False
            view.blocked_reasons = list(payload.get("blocked_reasons", view.blocked_reasons) or [])
            view.blocked_at = ts or view.blocked_at
            view.status = "send_blocked"

        elif et == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value:
            view.provider_name = payload.get("provider_name", view.provider_name)
            view.provider_status = payload.get("status", "requested")
            view.provider_requested_at = payload.get("requested_at", ts or view.provider_requested_at)
            view.provider_failure_reason = None

        elif et == EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value:
            view.provider_name = payload.get("provider_name", view.provider_name)
            view.provider_message_id = payload.get("provider_message_id", view.provider_message_id)
            view.provider_status = payload.get("status", "accepted")
            view.provider_accepted_at = payload.get("accepted_at", ts or view.provider_accepted_at)
            view.provider_failure_reason = None

        elif et == EventType.OUTBOUND_PROVIDER_SEND_FAILED.value:
            view.provider_name = payload.get("provider_name", view.provider_name)
            view.provider_status = payload.get("status", "failed")
            view.provider_failed_at = payload.get("failed_at", ts or view.provider_failed_at)
            view.provider_failure_reason = payload.get("failure_reason", view.provider_failure_reason)

        elif et == EventType.OUTBOUND_SENT.value:
            view.outbox_ready = False
            view.blocked_reasons = []
            view.blocked_at = None
            view.sent_at = ts
            view.status = "sent"

        elif et == EventType.REPLY_RECEIVED.value:
            view.last_reply_key = payload.get("reply_key", view.last_reply_key)
            view.reply_triage_status = "received"
            view.last_reply_received_at = payload.get("received_at", view.last_reply_received_at)
            view.last_reply_text_snippet = payload.get("reply_text_snippet", view.last_reply_text_snippet)
            view.reply_triage_error_type = None
            view.reply_triage_error_message = None

        elif et == EventType.REPLY_CLASSIFIED.value:
            view.last_reply_key = payload.get("reply_key", view.last_reply_key)
            classification = payload.get("classification", view.last_reply_classification)
            view.reply_triage_status = "classified"
            view.last_reply_classification = classification
            view.last_reply_received_at = payload.get("received_at", view.last_reply_received_at)
            view.last_reply_text_snippet = payload.get("reply_text_snippet", view.last_reply_text_snippet)
            view.reply_out_of_office = classification == "out_of_office"
            view.reply_triage_error_type = None
            view.reply_triage_error_message = None

        elif et == EventType.LEAD_INTERESTED.value:
            view.lead_interested = True
            view.lead_rejected = False

        elif et == EventType.LEAD_REJECTED.value:
            view.lead_rejected = True
            view.lead_interested = False

        elif et == EventType.UNSUBSCRIBE_RECORDED.value:
            view.unsubscribe_recorded = True
            view.marketing_suppressed = True
            view.marketing_suppression_reason = "unsubscribe"

        elif et == EventType.REPLY_TRIAGE_FAILED.value:
            view.last_reply_key = payload.get("reply_key", view.last_reply_key)
            view.reply_triage_status = "failed"
            view.last_reply_received_at = payload.get("received_at", view.last_reply_received_at)
            view.reply_triage_error_type = payload.get("error_type", view.reply_triage_error_type)
            view.reply_triage_error_message = payload.get("error_message", view.reply_triage_error_message)

        elif et == EventType.OUTCOME_RECORDED.value:
            view.latest_outcome = payload.get("outcome_category", view.latest_outcome)
            view.learning_outcome_version = payload.get("outcome_version", view.learning_outcome_version)
            view.learning_last_updated_at = ts or view.learning_last_updated_at

        elif et == EventType.SCORING_FEEDBACK_GENERATED.value:
            view.learning_outcome_version = payload.get("outcome_version", view.learning_outcome_version)
            view.learning_source_quality = payload.get("source_quality", view.learning_source_quality)
            view.learning_template_effectiveness = payload.get(
                "template_effectiveness",
                view.learning_template_effectiveness,
            )
            view.learning_reply_signal_strength = payload.get(
                "reply_signal_strength",
                view.learning_reply_signal_strength,
            )
            view.learning_last_updated_at = ts or view.learning_last_updated_at

        elif et == EventType.SOURCE_PERFORMANCE_UPDATED.value:
            view.learning_source_quality = payload.get("source_quality", view.learning_source_quality)
            view.learning_source_performance_note = payload.get(
                "performance_note",
                view.learning_source_performance_note,
            )
            view.learning_last_updated_at = ts or view.learning_last_updated_at

        elif et == EventType.TEMPLATE_PERFORMANCE_UPDATED.value:
            view.learning_template_effectiveness = payload.get(
                "template_effectiveness",
                view.learning_template_effectiveness,
            )
            view.learning_template_performance_note = payload.get(
                "performance_note",
                view.learning_template_performance_note,
            )
            view.learning_last_updated_at = ts or view.learning_last_updated_at

        elif et == EventType.DATA_REDACTION_APPLIED.value:
            if payload.get("reply_key") == view.last_reply_key:
                view.reply_text_redacted = True
                view.reply_text_redacted_at = payload.get("applied_at", view.reply_text_redacted_at)
                view.last_reply_text_snippet = payload.get("replacement_text", view.last_reply_text_snippet)

        elif et == EventType.RETENTION_REVIEWED.value:
            if payload.get("reply_key") == view.last_reply_key:
                view.retention_status = payload.get("action", view.retention_status)
                view.retention_last_reviewed_at = payload.get("reviewed_at", view.retention_last_reviewed_at)
                reason = payload.get("reason")
                if reason and reason not in view.retention_notes:
                    view.retention_notes.append(reason)

    overlays = redaction_overlays()
    for view in state.values():
        if view.last_reply_key and view.last_reply_key in overlays:
            overlay = overlays[view.last_reply_key]
            view.reply_text_redacted = True
            view.reply_text_redacted_at = overlay.get("applied_at", view.reply_text_redacted_at)
            view.last_reply_text_snippet = overlay.get("replacement_text", view.last_reply_text_snippet)
            note = overlay.get("reason")
            if note and note not in view.retention_notes:
                view.retention_notes.append(str(note))

        suppressions = active_suppressions_for_entity(view)
        view.active_suppressions = suppressions
        if suppressions:
            view.marketing_suppressed = True
            if not view.marketing_suppression_reason:
                view.marketing_suppression_reason = str(suppressions[-1].get("reason"))

        subject_requests = subject_requests_for_entity(view)
        view.subject_request_summaries = subject_requests
        if subject_requests:
            latest = subject_requests[-1]
            view.latest_subject_request_id = latest.get("request_id")
            view.latest_subject_request_type = latest.get("request_type")
            view.latest_subject_request_status = latest.get("status")
            view.latest_subject_request_updated_at = latest.get("updated_at") or latest.get("requested_at")

    return state


def rank_pipeline(views: List[PipelineEntityView]) -> List[PipelineEntityView]:
    def key(v: PipelineEntityView):
        stage_weight = {
            "candidate_ingested": 6,
            "qualified": 5,
            "draft_created": 4,
            "approved": 3,
            "outbox_ready": 2,
            "send_blocked": 2,
            "rejected": 1,
            "sent": 0,
        }.get(v.status, 0)

        return (v.priority_score, v.estimated_containers_per_month, stage_weight, -v.risk_score)

    return sorted(views, key=key, reverse=True)


def entity_timeline(entity_id: str) -> List[dict]:
    out: List[dict] = []
    for rec in ledger.read():
        if rec.get("entity_id") == entity_id:
            out.append(rec)
    return out
