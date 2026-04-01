from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.compliance import evaluate_compliance
from supply_program_engine.enrichment import latest_completed_enrichment
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.models import Candidate, EventType, Qualification
from supply_program_engine.qualification import qualify

log = get_logger("supply_program_engine")


def _qualification_event_id(candidate_payload: dict, enrichment_event_id: str | None = None) -> str:
    return ledger.generate_event_id(
        {
            "event_type": EventType.QUALIFICATION_COMPUTED.value,
            "candidate": candidate_payload,
            "enrichment_event_id": enrichment_event_id or "none",
        }
    )


def _apply_enrichment_to_qualification(base_q: Qualification, enrichment_payload: dict | None) -> Qualification:
    if not enrichment_payload:
        return base_q

    evidence = list(base_q.evidence)
    notes = [base_q.notes] if base_q.notes else []

    if enrichment_payload.get("website_present"):
        evidence.append("enrichment_website_present")
    if enrichment_payload.get("contact_page_detected"):
        evidence.append("enrichment_contact_page_detected")
    if enrichment_payload.get("construction_keywords_found"):
        evidence.append("enrichment_construction_keywords_found")
    if enrichment_payload.get("distributor_keywords_found"):
        evidence.append("enrichment_distributor_keywords_found")
    if enrichment_payload.get("likely_b2b"):
        evidence.append("enrichment_likely_b2b")

    segment = base_q.segment
    priority_score = base_q.priority_score
    decision_maker_type = base_q.decision_maker_type

    if segment == "unknown" and enrichment_payload.get("distributor_keywords_found"):
        segment = "industrial_distributor"
        priority_score = max(priority_score, 6)
        decision_maker_type = "Procurement"
        notes.append("segment supported by deterministic enrichment heuristics")

    return Qualification(
        segment=segment,
        priority_score=priority_score,
        estimated_containers_per_month=base_q.estimated_containers_per_month,
        decision_maker_type=decision_maker_type,
        notes="; ".join(note for note in notes if note) or None,
        evidence=evidence,
        scoring_version=base_q.scoring_version,
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
        enrichment = latest_completed_enrichment(entity_id)

        q_event_id = _qualification_event_id(candidate_payload, enrichment.get("event_id") if enrichment else None)
        processed += 1

        if ledger.exists(q_event_id):
            skipped_duplicates += 1
            continue

        candidate = Candidate(**candidate_payload)
        base_q = _apply_enrichment_to_qualification(qualify(candidate), (enrichment or {}).get("payload"))
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
            extra={
                "correlation_id": cid,
                "entity_id": entity_id,
                "event_id": q_event_id,
                "enrichment_event_id": enrichment.get("event_id") if enrichment else None,
            },
        )

    return {"processed": processed, "emitted": emitted, "skipped_duplicates": skipped_duplicates}
