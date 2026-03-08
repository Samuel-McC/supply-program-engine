from __future__ import annotations

from supply_program_engine.models import Candidate, Qualification
from supply_program_engine.scoring.engine import score_candidate


def qualify(candidate: Candidate) -> Qualification:
    """
    Phase 7 qualification now delegates to the policy scoring engine.
    """
    return score_candidate(candidate)