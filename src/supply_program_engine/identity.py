from __future__ import annotations

import hashlib

from supply_program_engine.models import Candidate


def stable_entity_id(candidate: Candidate) -> str:
    """
    Stable identity preference:
    1. website
    2. external_id + source
    3. company_name + location
    """
    if candidate.website and candidate.website.strip():
        basis = candidate.website.strip().lower()
    elif candidate.external_id and candidate.source:
        basis = f"{candidate.source.strip().lower()}|{candidate.external_id.strip().lower()}"
    else:
        basis = f"{candidate.company_name.strip().lower()}|{candidate.location.strip().lower()}"

    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
