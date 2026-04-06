from __future__ import annotations

from supply_program_engine.ai.models import AIDraftContext


AI_DRAFT_PROMPT_VERSION = "ai_draft_personalizer_v1"


def build_draft_prompt(context: AIDraftContext) -> str:
    enrichment = ", ".join(context.enrichment_summary) if context.enrichment_summary else "none"
    return (
        "Create an advisory outreach variant.\n"
        f"Company: {context.company_name}\n"
        f"Segment: {context.segment}\n"
        f"Location: {context.location or 'unknown'}\n"
        f"Source: {context.source or 'unknown'}\n"
        f"Discovered Via: {context.discovered_via or 'unknown'}\n"
        f"Source Query: {context.source_query or 'unknown'}\n"
        f"Source Region: {context.source_region or 'unknown'}\n"
        f"Enrichment Summary: {enrichment}\n"
        f"Deterministic Subject: {context.deterministic_subject}\n"
        f"Deterministic Body:\n{context.deterministic_body}\n"
        "Return a more personalized but still concise opening and subject suggestion.\n"
        "Do not approve, send, or change workflow semantics."
    )
