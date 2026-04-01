from __future__ import annotations

from typing import Dict, List

from supply_program_engine import ledger
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

        elif et == EventType.OUTBOUND_DRAFT_CREATED.value:
            view.draft_id = payload.get("draft_id", view.draft_id) or rec.get("event_id")
            view.draft_subject = payload.get("subject", view.draft_subject)
            view.draft_body = payload.get("body", view.draft_body)
            view.template_version = payload.get("template_version", view.template_version)
            view.status = "draft_created"

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

        elif et == EventType.OUTBOUND_SENT.value:
            view.outbox_ready = False
            view.blocked_reasons = []
            view.blocked_at = None
            view.sent_at = ts
            view.status = "sent"

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
