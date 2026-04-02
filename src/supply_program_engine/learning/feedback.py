from __future__ import annotations

from supply_program_engine.learning.outcomes import OUTCOME_VERSION, OutcomeResult
from supply_program_engine.models import PipelineEntityView


def _source_quality(outcome_category: str) -> str:
    if outcome_category == "reply_interested":
        return "strong"
    if outcome_category in {"reply_rejected", "unsubscribe"}:
        return "weak"
    return "neutral"


def _template_effectiveness(outcome_category: str) -> str:
    if outcome_category == "reply_interested":
        return "positive"
    if outcome_category in {"reply_rejected", "unsubscribe"}:
        return "negative"
    return "neutral"


def _reply_signal_strength(outcome_category: str) -> str:
    if outcome_category in {"reply_interested", "unsubscribe"}:
        return "high"
    if outcome_category in {"reply_rejected", "out_of_office"}:
        return "medium"
    return "low"


def build_feedback_payload(entity: PipelineEntityView, outcome: OutcomeResult) -> dict[str, object]:
    outcome_category = outcome.category
    source_quality = _source_quality(outcome_category)
    template_effectiveness = _template_effectiveness(outcome_category)
    reply_signal_strength = _reply_signal_strength(outcome_category)

    return {
        "outcome_version": OUTCOME_VERSION,
        "outcome_category": outcome_category,
        "source": entity.source,
        "segment": entity.segment,
        "template_version": entity.template_version,
        "reply_classification": entity.last_reply_classification,
        "source_quality": source_quality,
        "template_effectiveness": template_effectiveness,
        "reply_signal_strength": reply_signal_strength,
        "counts": {
            "observations": 1,
            "positive": 1 if outcome_category == "reply_interested" else 0,
            "negative": 1 if outcome_category in {"reply_rejected", "unsubscribe"} else 0,
        },
    }


def source_performance_note(entity: PipelineEntityView, feedback_payload: dict[str, object]) -> str:
    source = entity.source or "unknown_source"
    segment = entity.segment or "unknown"
    quality = feedback_payload["source_quality"]
    outcome = feedback_payload["outcome_category"]
    return f"{source} / {segment}: {quality} ({outcome})"


def template_performance_note(entity: PipelineEntityView, feedback_payload: dict[str, object]) -> str:
    template_version = entity.template_version or "unknown_template"
    effect = feedback_payload["template_effectiveness"]
    outcome = feedback_payload["outcome_category"]
    return f"{template_version}: {effect} ({outcome})"
