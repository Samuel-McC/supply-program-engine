from __future__ import annotations

from supply_program_engine.models import Candidate, Qualification


def evaluate_compliance(candidate: Candidate, qualification: Qualification) -> dict:
    """
    Deterministic compliance/risk checks.

    Returns a dict so it can be embedded directly into event payloads.
    """
    findings: list[str] = []
    risk_score = 0
    requires_manual_review = False

    website = (candidate.website or "").strip().lower()
    company_name = (candidate.company_name or "").strip().lower()

    if not website:
        findings.append("missing website")
        risk_score += 3
        requires_manual_review = True

    if qualification.segment == "unknown":
        findings.append("unknown segment")
        risk_score += 3
        requires_manual_review = True

    if qualification.priority_score <= 3:
        findings.append("low confidence qualification")
        risk_score += 2
        requires_manual_review = True

    if "gmail.com" in website or "yahoo.com" in website or "hotmail.com" in website:
        findings.append("consumer email/domain style website detected")
        risk_score += 2
        requires_manual_review = True

    if len(company_name) < 4:
        findings.append("weak company name signal")
        risk_score += 1

    if not findings:
        findings.append("no compliance issues detected")

    return {
        "risk_score": risk_score,
        "requires_manual_review": requires_manual_review,
        "policy_version": "v1",
        "findings": findings,
    }