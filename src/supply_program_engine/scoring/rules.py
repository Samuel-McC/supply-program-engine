from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from supply_program_engine.models import Candidate


@dataclass
class RuleResult:
    score_delta: int
    estimated_volume_delta: int
    segment_override: str | None
    decision_maker_type: str | None
    evidence: list[str]
    notes: list[str]
    risk_delta: int = 0
    requires_manual_review: bool = False


RuleFn = Callable[[Candidate], RuleResult]


def _candidate_text(candidate: Candidate) -> str:
    return " ".join(
        [
            candidate.company_name or "",
            candidate.website or "",
            candidate.location or "",
            candidate.source or "",
            candidate.discovered_via or "",
        ]
    ).lower()


def distributor_rule(candidate: Candidate) -> RuleResult:
    text = _candidate_text(candidate)
    keywords = ["distributor", "wholesale", "wholesaler", "lumber", "import", "building materials"]

    matched = [k for k in keywords if k in text]
    if not matched:
        return RuleResult(0, 0, None, None, [], [])

    return RuleResult(
        score_delta=10,
        estimated_volume_delta=30,
        segment_override="industrial_distributor",
        decision_maker_type="Procurement / Purchasing Manager",
        evidence=[f"matched keyword: {k}" for k in matched],
        notes=["Distributor/importer pattern matched"],
    )


def regional_supplier_rule(candidate: Candidate) -> RuleResult:
    text = _candidate_text(candidate)
    keywords = ["building supply", "building supplier", "merchant", "yard", "supplier"]

    matched = [k for k in keywords if k in text]
    if not matched:
        return RuleResult(0, 0, None, None, [], [])

    return RuleResult(
        score_delta=8,
        estimated_volume_delta=12,
        segment_override="regional_building_supplier",
        decision_maker_type="Branch Manager / Buyer",
        evidence=[f"matched keyword: {k}" for k in matched],
        notes=["Regional supplier pattern matched"],
    )


def contractor_rule(candidate: Candidate) -> RuleResult:
    text = _candidate_text(candidate)
    keywords = ["concrete", "formwork", "scaffold", "scaffolding", "shoring"]

    matched = [k for k in keywords if k in text]
    if not matched:
        return RuleResult(0, 0, None, None, [], [])

    return RuleResult(
        score_delta=7,
        estimated_volume_delta=6,
        segment_override="concrete_contractor_large",
        decision_maker_type="Ops Manager / Superintendent",
        evidence=[f"matched keyword: {k}" for k in matched],
        notes=["Concrete/formwork contractor pattern matched"],
    )


def modular_rule(candidate: Candidate) -> RuleResult:
    text = _candidate_text(candidate)
    keywords = ["modular", "prefab", "manufactured housing"]

    matched = [k for k in keywords if k in text]
    if not matched:
        return RuleResult(0, 0, None, None, [], [])

    return RuleResult(
        score_delta=8,
        estimated_volume_delta=15,
        segment_override="modular_manufacturer",
        decision_maker_type="Supply Chain / Procurement Lead",
        evidence=[f"matched keyword: {k}" for k in matched],
        notes=["Modular manufacturing pattern matched"],
    )


def unknown_rule(candidate: Candidate) -> RuleResult:
    return RuleResult(
        score_delta=3,
        estimated_volume_delta=1,
        segment_override="unknown",
        decision_maker_type="Unknown",
        evidence=["no strong keyword match"],
        notes=["Insufficient deterministic signal"],
        risk_delta=1,
        requires_manual_review=True,
    )


ALL_RULES: list[RuleFn] = [
    distributor_rule,
    regional_supplier_rule,
    contractor_rule,
    modular_rule,
]