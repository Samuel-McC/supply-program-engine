from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.learning.feedback import (
    build_feedback_payload,
    source_performance_note,
    template_performance_note,
)
from supply_program_engine.learning.outcomes import OUTCOME_VERSION, derive_outcome
from supply_program_engine.logging import get_logger
from supply_program_engine.models import EventType
from supply_program_engine.observability import trace_span
from supply_program_engine.projections import build_pipeline_state

log = get_logger("supply_program_engine")


def _event_id(event_type: EventType, entity_id: str, payload: dict[str, object]) -> str:
    return ledger.generate_event_id(
        {
            "event_type": event_type.value,
            "entity_id": entity_id,
            "payload": payload,
        }
    )


def run_once(limit: int = 50) -> dict:
    processed = 0
    outcomes_recorded = 0
    feedback_generated = 0
    source_updates = 0
    template_updates = 0
    skipped_duplicates = 0

    with trace_span("runner.learning.batch", task_type="learning_run", extra={"limit": limit}):
        for entity in build_pipeline_state().values():
            if processed >= limit:
                break

            outcome = derive_outcome(entity)
            if outcome is None:
                continue

            processed += 1

            with trace_span(
                "runner.learning.entity",
                correlation_id=entity.correlation_id,
                entity_id=entity.entity_id,
                event_type=EventType.OUTCOME_RECORDED.value,
                extra={"outcome_category": outcome.category},
            ):
                outcome_payload = {
                    "outcome_version": OUTCOME_VERSION,
                    "outcome_category": outcome.category,
                    "source": entity.source,
                    "segment": entity.segment,
                    "template_version": entity.template_version,
                    "reply_classification": entity.last_reply_classification,
                    "basis": outcome.basis,
                }
                outcome_event_id = _event_id(EventType.OUTCOME_RECORDED, entity.entity_id, outcome_payload)

                if ledger.exists(outcome_event_id):
                    skipped_duplicates += 1
                    continue

                ledger.append(
                    {
                        "event_id": outcome_event_id,
                        "event_type": EventType.OUTCOME_RECORDED.value,
                        "correlation_id": entity.correlation_id or "learning-runner",
                        "entity_id": entity.entity_id,
                        "payload": outcome_payload,
                    }
                )
                outcomes_recorded += 1

                feedback_payload = build_feedback_payload(entity, outcome)
                scoring_event_id = _event_id(EventType.SCORING_FEEDBACK_GENERATED, entity.entity_id, feedback_payload)
                if not ledger.exists(scoring_event_id):
                    ledger.append(
                        {
                            "event_id": scoring_event_id,
                            "event_type": EventType.SCORING_FEEDBACK_GENERATED.value,
                            "correlation_id": entity.correlation_id or "learning-runner",
                            "entity_id": entity.entity_id,
                            "payload": feedback_payload,
                        }
                    )
                    feedback_generated += 1

                if entity.source:
                    source_payload = {
                        **feedback_payload,
                        "performance_note": source_performance_note(entity, feedback_payload),
                    }
                    source_event_id = _event_id(EventType.SOURCE_PERFORMANCE_UPDATED, entity.entity_id, source_payload)
                    if not ledger.exists(source_event_id):
                        ledger.append(
                            {
                                "event_id": source_event_id,
                                "event_type": EventType.SOURCE_PERFORMANCE_UPDATED.value,
                                "correlation_id": entity.correlation_id or "learning-runner",
                                "entity_id": entity.entity_id,
                                "payload": source_payload,
                            }
                        )
                        source_updates += 1

                if entity.template_version:
                    template_payload = {
                        **feedback_payload,
                        "performance_note": template_performance_note(entity, feedback_payload),
                    }
                    template_event_id = _event_id(EventType.TEMPLATE_PERFORMANCE_UPDATED, entity.entity_id, template_payload)
                    if not ledger.exists(template_event_id):
                        ledger.append(
                            {
                                "event_id": template_event_id,
                                "event_type": EventType.TEMPLATE_PERFORMANCE_UPDATED.value,
                                "correlation_id": entity.correlation_id or "learning-runner",
                                "entity_id": entity.entity_id,
                                "payload": template_payload,
                            }
                        )
                        template_updates += 1

                log.info(
                    "learning_feedback_generated",
                    extra={
                        "entity_id": entity.entity_id,
                        "outcome_category": outcome.category,
                        "outcome_version": OUTCOME_VERSION,
                    },
                )

    return {
        "processed": processed,
        "outcomes_recorded": outcomes_recorded,
        "feedback_generated": feedback_generated,
        "source_updates": source_updates,
        "template_updates": template_updates,
        "skipped_duplicates": skipped_duplicates,
    }
