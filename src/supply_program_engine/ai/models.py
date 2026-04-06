from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AIDraftContext(BaseModel):
    entity_id: str
    company_name: str
    location: str | None = None
    segment: str
    source: str | None = None
    discovered_via: str | None = None
    source_query: str | None = None
    source_region: str | None = None
    enrichment_summary: list[str] = Field(default_factory=list)
    deterministic_draft_id: str
    deterministic_subject: str
    deterministic_body: str
    deterministic_template_version: str | None = None
    deterministic_generation_mode: str = "deterministic"


class AIDraftSuggestion(BaseModel):
    provider_name: str
    model_name: str
    prompt_version: str
    generated_at: str
    provider_response_id: str | None = None
    suggested_subject: str
    suggested_opening: str
    suggested_body: str | None = None
    generation_mode: Literal["ai_advisory"] = "ai_advisory"
    usage_metadata: dict[str, object] = Field(default_factory=dict)
    provider_metadata: dict[str, object] = Field(default_factory=dict)


class AIDraftFailure(BaseModel):
    provider_name: str
    model_name: str
    prompt_version: str
    failed_at: str
    provider_response_id: str | None = None
    failure_reason: str
    generation_mode: Literal["ai_advisory"] = "ai_advisory"
    provider_metadata: dict[str, object] = Field(default_factory=dict)
