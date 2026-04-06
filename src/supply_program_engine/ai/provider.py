from __future__ import annotations

from typing import Protocol

from supply_program_engine.ai.models import AIDraftContext, AIDraftSuggestion
from supply_program_engine.config import settings
from supply_program_engine.data_controls.models import iso_now


class AIProviderError(RuntimeError):
    pass


class AIDraftProvider(Protocol):
    provider_name: str
    model_name: str

    def suggest_draft(self, *, context: AIDraftContext, prompt: str, prompt_version: str) -> AIDraftSuggestion:
        ...


def _opening_paragraph(context: AIDraftContext) -> str:
    if context.source_query:
        return (
            f"We noticed {context.company_name}'s public footprint around {context.source_query} "
            f"in {context.source_region or context.location or 'your region'}, and thought a more tailored panel supply conversation could be relevant."
        )
    if "distributor_keywords_found" in context.enrichment_summary:
        return (
            f"Your public website suggests active distributor-led procurement, so I wanted to share a more relevant panel supply option for {context.company_name}."
        )
    if "construction_keywords_found" in context.enrichment_summary:
        return (
            f"Your public website suggests active construction or formwork work, which made {context.company_name} look like a strong fit for a reusable panel supply conversation."
        )
    if context.discovered_via:
        return (
            f"We came across {context.company_name} through {context.discovered_via}, and thought a more tailored supply introduction might be useful."
        )
    return (
        f"I wanted to share a more tailored supply introduction for {context.company_name} based on your {context.segment.replace('_', ' ')} profile."
    )


class MockAIDraftProvider:
    provider_name = "mock"

    def __init__(self, model_name: str):
        self.model_name = model_name

    def suggest_draft(self, *, context: AIDraftContext, prompt: str, prompt_version: str) -> AIDraftSuggestion:
        greeting = f"Hi {context.company_name or 'there'},"
        opening = _opening_paragraph(context)
        body_sections = [section for section in context.deterministic_body.split("\n\n") if section.strip()]
        tail_sections = body_sections[2:] if len(body_sections) > 2 else body_sections[1:]
        suggested_subject = f"{context.company_name}: tailored panel supply idea"
        suggested_body_sections = [greeting, opening, *tail_sections]
        suggested_body = "\n\n".join(section for section in suggested_body_sections if section.strip())
        return AIDraftSuggestion(
            provider_name=self.provider_name,
            model_name=self.model_name,
            prompt_version=prompt_version,
            generated_at=iso_now(),
            suggested_subject=suggested_subject,
            suggested_opening=opening,
            suggested_body=suggested_body,
            provider_metadata={"mock_provider": True, "prompt_chars": len(prompt)},
        )


def resolve_provider() -> AIDraftProvider:
    if not settings.AI_ENABLED:
        raise AIProviderError("ai_disabled")
    if not settings.AI_DRAFTS_ENABLED:
        raise AIProviderError("ai_drafts_disabled")
    if settings.AI_PROVIDER == "mock":
        return MockAIDraftProvider(model_name=settings.AI_MODEL)
    raise AIProviderError(f"unsupported_provider:{settings.AI_PROVIDER}")
