from __future__ import annotations

import json
from typing import Protocol

import requests

from supply_program_engine.ai.models import AIDraftContext, AIDraftSuggestion
from supply_program_engine.ai.prompts import AI_DRAFT_SCHEMA_NAME, AI_DRAFT_SYSTEM_PROMPT, draft_response_schema
from supply_program_engine.config import settings
from supply_program_engine.data_controls.models import iso_now


class AIProviderError(RuntimeError):
    pass


class AIDraftProvider(Protocol):
    provider_name: str
    model_name: str

    def suggest_draft(self, *, context: AIDraftContext, prompt: str, prompt_version: str) -> AIDraftSuggestion:
        ...


def _usage_metadata(payload: dict[str, object]) -> dict[str, object]:
    usage = payload.get("usage")
    return usage if isinstance(usage, dict) else {}


def _response_text(payload: dict[str, object]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        raise AIProviderError("openai_invalid_response:no_output")

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                return str(part["text"])

    raise AIProviderError("openai_invalid_response:no_output_text")


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    body = response.text.strip()
    return body or f"http_{response.status_code}"


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


class OpenAIDraftProvider:
    provider_name = "openai"
    _responses_url = "https://api.openai.com/v1/responses"

    def __init__(self, model_name: str, api_key: str | None):
        self.model_name = model_name
        self.api_key = api_key

    def suggest_draft(self, *, context: AIDraftContext, prompt: str, prompt_version: str) -> AIDraftSuggestion:
        if not self.api_key:
            raise AIProviderError("openai_api_key_missing")

        payload = {
            "model": self.model_name,
            "store": False,
            "input": [
                {"role": "system", "content": AI_DRAFT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": AI_DRAFT_SCHEMA_NAME,
                    "schema": draft_response_schema(),
                    "strict": True,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self._responses_url, headers=headers, json=payload, timeout=15)
        except requests.RequestException as exc:
            raise AIProviderError(f"openai_request_failed:{exc.__class__.__name__}") from exc

        if response.status_code >= 400:
            raise AIProviderError(f"openai_api_error:{response.status_code}:{_error_detail(response)}")

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AIProviderError("openai_invalid_response:json_decode") from exc

        try:
            parsed = json.loads(_response_text(response_payload))
        except json.JSONDecodeError as exc:
            raise AIProviderError("openai_invalid_response:structured_output_decode") from exc

        if not isinstance(parsed, dict):
            raise AIProviderError("openai_invalid_response:structured_output_shape")

        subject = parsed.get("suggested_subject")
        opening = parsed.get("suggested_opening")
        body = parsed.get("suggested_body")
        if not all(isinstance(value, str) and value.strip() for value in (subject, opening, body)):
            raise AIProviderError("openai_invalid_response:missing_fields")

        return AIDraftSuggestion(
            provider_name=self.provider_name,
            model_name=self.model_name,
            prompt_version=prompt_version,
            generated_at=iso_now(),
            provider_response_id=response_payload.get("id") if isinstance(response_payload.get("id"), str) else None,
            suggested_subject=subject.strip(),
            suggested_opening=opening.strip(),
            suggested_body=body.strip(),
            usage_metadata=_usage_metadata(response_payload),
            provider_metadata={
                "response_status": response_payload.get("status"),
                "request_id": response.headers.get("x-request-id"),
            },
        )


def resolve_provider() -> AIDraftProvider:
    if not settings.AI_ENABLED:
        raise AIProviderError("ai_disabled")
    if not settings.AI_DRAFTS_ENABLED:
        raise AIProviderError("ai_drafts_disabled")
    if settings.AI_PROVIDER == "mock":
        return MockAIDraftProvider(model_name=settings.AI_MODEL)
    if settings.AI_PROVIDER == "openai":
        return OpenAIDraftProvider(model_name=settings.AI_MODEL, api_key=settings.OPENAI_API_KEY)
    raise AIProviderError(f"unsupported_provider:{settings.AI_PROVIDER}")
