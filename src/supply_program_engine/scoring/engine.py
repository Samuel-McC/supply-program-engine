from __future__ import annotations

from supply_program_engine.models import Candidate, Qualification
from supply_program_engine.scoring.rules import ALL_RULES, unknown_rule


def score_candidate(candidate: Candidate) -> Qualification:
    """
    Deterministic scoring engine.

    Applies multiple rule packs, selects the strongest matching rule result,
    and produces an auditable Qualification object.
    """
    results = [rule(candidate) for rule in ALL_RULES]
    matched = [r for r in results if r.segment_override is not None]

    if not matched:
        fallback = unknown_rule(candidate)
        return Qualification(
            segment=fallback.segment_override or "unknown",
            priority_score=fallback.score_delta,
            estimated_containers_per_month=fallback.estimated_volume_delta,
            decision_maker_type=fallback.decision_maker_type or "Unknown",
            notes="; ".join(fallback.notes),
            evidence=fallback.evidence,
            scoring_version="v2_policy_engine",
        )

    best = max(matched, key=lambda r: (r.score_delta, r.estimated_volume_delta))

    return Qualification(
        segment=best.segment_override or "unknown",
        priority_score=best.score_delta,
        estimated_containers_per_month=best.estimated_volume_delta,
        decision_maker_type=best.decision_maker_type or "Unknown",
        notes="; ".join(best.notes),
        evidence=best.evidence,
        scoring_version="v2_policy_engine",
    )