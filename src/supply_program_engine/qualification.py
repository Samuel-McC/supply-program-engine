from __future__ import annotations

from supply_program_engine.models import Candidate, Qualification


def qualify(candidate: Candidate) -> Qualification:
    """
    Deterministic rules only.
    No LLM. No external calls.
    """

    text = " ".join(
        [
            candidate.company_name or "",
            candidate.discovered_via or "",
            candidate.source or "",
            candidate.location or "",
            candidate.website or "",
        ]
    ).lower()

    # Segment rules (simple but effective baseline)
    if any(k in text for k in ["distributor", "wholesale", "wholesaler", "lumber", "building materials", "import"]):
        return Qualification(
            segment="industrial_distributor",
            priority_score=10,
            estimated_containers_per_month=30,
            decision_maker_type="Procurement / Purchasing Manager",
            notes="High absorption potential if qualified importer/distributor.",
        )

    if any(k in text for k in ["building supplier", "building supply", "merchant", "yard", "supplier"]):
        return Qualification(
            segment="regional_building_supplier",
            priority_score=8,
            estimated_containers_per_month=12,
            decision_maker_type="Branch Manager / Buyer",
            notes="Regional supplier with decent repeat volume.",
        )

    if any(k in text for k in ["concrete", "formwork", "scaffold", "scaffolding", "shoring"]):
        return Qualification(
            segment="concrete_contractor_large",
            priority_score=7,
            estimated_containers_per_month=6,
            decision_maker_type="Ops Manager / Superintendent",
            notes="Jobsite-driven purchases; pitch reuse cycles vs OSB.",
        )

    if any(k in text for k in ["modular", "prefab", "manufactured housing"]):
        return Qualification(
            segment="modular_manufacturer",
            priority_score=8,
            estimated_containers_per_month=15,
            decision_maker_type="Supply Chain / Procurement Lead",
            notes="Program-style buyer; consistency matters.",
        )

    return Qualification(
        segment="unknown",
        priority_score=3,
        estimated_containers_per_month=1,
        decision_maker_type="Unknown",
        notes="Insufficient signal; requires human/agent enrichment.",
    )