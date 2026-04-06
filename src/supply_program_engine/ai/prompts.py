from __future__ import annotations

from supply_program_engine.ai.models import AIDraftContext


AI_DRAFT_PROMPT_VERSION = "ai_draft_personalizer_v1"
AI_DRAFT_SCHEMA_NAME = "ai_draft_suggestion"
AI_DRAFT_SYSTEM_PROMPT = (
    "You create advisory-only B2B outreach personalization suggestions. "
    "You do not approve, send, change workflow state, or bypass policy. "
    "Use only the provided business context and deterministic draft as source material."
)


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


def draft_response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "suggested_subject": {
                "type": "string",
                "description": "A concise subject line for the advisory outreach variant.",
            },
            "suggested_opening": {
                "type": "string",
                "description": "A tailored opening paragraph for the outreach draft.",
            },
            "suggested_body": {
                "type": "string",
                "description": "A complete advisory body variant that keeps the deterministic draft intent.",
            },
        },
        "required": ["suggested_subject", "suggested_opening", "suggested_body"],
        "additionalProperties": False,
    }
