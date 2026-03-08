from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.compliance import evaluate_compliance
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import Candidate, EventType, Qualification
from supply_program_engine.qualification import qualify

log = get_logger("supply_program_engine")


def _qualification_event_id(candidate_payload: dict) -> str:
    return ledger.generate_event_id(
        {"event_type": EventType.QUALIFICATION_COMPUTED.value, "candidate": candidate_payload}
    )


def run_once(limit: int = 50) -> dict:
    processed = 0
    emitted = 0
    skipped_duplicates = 0

    for rec in ledger.read():
        if processed >= limit:
            break

        if rec.get("event_type") != EventType.CANDIDATE_INGESTED.value:
            continue

        candidate_payload = rec.get("payload") or {}
        entity_id = rec.get("entity_id") or "unknown"
        cid = rec.get("correlation_id") or generate_correlation_id()

        q_event_id = _qualification_event_id(candidate_payload)
        processed += 1

        if ledger.exists(q_event_id):
            skipped_duplicates += 1
            continue

        candidate = Candidate(**candidate_payload)
        base_q = qualify(candidate)
        compliance = evaluate_compliance(candidate, base_q)

        q = Qualification(
            segment=base_q.segment,
            priority_score=base_q.priority_score,
            estimated_containers_per_month=base_q.estimated_containers_per_month,
            decision_maker_type=base_q.decision_maker_type,
            notes=base_q.notes,
            evidence=base_q.evidence,
            scoring_version=base_q.scoring_version,
            risk_score=compliance["risk_score"],
            requires_manual_review=compliance["requires_manual_review"],
            policy_version=compliance["policy_version"],
            compliance_findings=compliance["findings"],
        )

        ledger.append(
            {
                "event_id": q_event_id,
                "event_type": EventType.QUALIFICATION_COMPUTED.value,
                "correlation_id": cid,
                "entity_id": entity_id,
                "payload": q.model_dump(),
            }
        )

        emitted += 1
        log.info(
            "qualification_emitted",
            extra={"correlation_id": cid, "entity_id": entity_id, "event_id": q_event_id},
        )

    return {"processed": processed, "emitted": emitted, "skipped_duplicates": skipped_duplicates}