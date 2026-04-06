from __future__ import annotations

from supply_program_engine import ledger
from supply_program_engine.ai.models import AIDraftContext, AIDraftFailure
from supply_program_engine.ai.prompts import AI_DRAFT_PROMPT_VERSION, build_draft_prompt
from supply_program_engine.ai.provider import AIProviderError, resolve_provider
from supply_program_engine.data_controls.models import iso_now
from supply_program_engine.logging import get_logger
from supply_program_engine.models import EventType
from supply_program_engine.observability import trace_span
from supply_program_engine.projections import build_pipeline_state

log = get_logger("supply_program_engine")


def _enrichment_summary(entity) -> list[str]:
    summary: list[str] = []
    if entity.enrichment_contact_page_detected:
        summary.append("contact_page_detected")
    if entity.enrichment_construction_keywords_found:
        summary.append("construction_keywords_found")
    if entity.enrichment_distributor_keywords_found:
        summary.append("distributor_keywords_found")
    if entity.enrichment_likely_b2b:
        summary.append("likely_b2b")
    return summary


def _failure_event_id(
    *,
    entity_id: str,
    source_draft_id: str | None,
    provider_name: str,
    model_name: str,
    prompt_version: str,
    failure_reason: str,
) -> str:
    return ledger.generate_event_id(
        {
            "event_type": EventType.AI_DRAFT_GENERATION_FAILED.value,
            "entity_id": entity_id,
            "source_draft_id": source_draft_id or "none",
            "provider_name": provider_name,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "failure_reason": failure_reason,
        }
    )


def _suggested_event_id(
    *,
    entity_id: str,
    source_draft_id: str,
    provider_name: str,
    model_name: str,
    prompt_version: str,
) -> str:
    return ledger.generate_event_id(
        {
            "event_type": EventType.AI_DRAFT_SUGGESTED.value,
            "entity_id": entity_id,
            "source_draft_id": source_draft_id,
            "provider_name": provider_name,
            "model_name": model_name,
            "prompt_version": prompt_version,
        }
    )


def generate_draft_suggestion(entity_id: str, correlation_id: str) -> dict[str, object]:
    state = build_pipeline_state()
    entity = state.get(entity_id)
    if entity is None:
        raise ValueError("entity_not_found")

    if not entity.draft_id or not entity.draft_subject or not entity.draft_body:
        failure_reason = "source_draft_missing"
        failure = AIDraftFailure(
            provider_name="unavailable",
            model_name="unavailable",
            prompt_version=AI_DRAFT_PROMPT_VERSION,
            failed_at=iso_now(),
            failure_reason=failure_reason,
        )
        event_id = _failure_event_id(
            entity_id=entity_id,
            source_draft_id=entity.draft_id,
            provider_name=failure.provider_name,
            model_name=failure.model_name,
            prompt_version=failure.prompt_version,
            failure_reason=failure_reason,
        )
        if ledger.exists(event_id):
            return {"status": "duplicate", "event_id": event_id, "entity_id": entity_id, "failure_reason": failure_reason}
        ledger.append(
            {
                "event_id": event_id,
                "event_type": EventType.AI_DRAFT_GENERATION_FAILED.value,
                "correlation_id": correlation_id,
                "entity_id": entity_id,
                "payload": {
                    "entity_id": entity_id,
                    "source_draft_id": entity.draft_id,
                    **failure.model_dump(),
                },
            }
        )
        return {"status": "failed", "event_id": event_id, "entity_id": entity_id, "failure_reason": failure_reason}

    context = AIDraftContext(
        entity_id=entity.entity_id,
        company_name=entity.company_name,
        location=entity.location,
        segment=entity.segment,
        source=entity.source,
        discovered_via=entity.discovered_via,
        source_query=entity.source_query,
        source_region=entity.source_region,
        enrichment_summary=_enrichment_summary(entity),
        deterministic_draft_id=entity.draft_id,
        deterministic_subject=entity.draft_subject,
        deterministic_body=entity.draft_body,
        deterministic_template_version=entity.template_version,
    )
    prompt_version = AI_DRAFT_PROMPT_VERSION

    with trace_span(
        "runner.ai_draft_suggestion",
        correlation_id=correlation_id,
        entity_id=entity_id,
        event_type=EventType.AI_DRAFT_SUGGESTED.value,
        extra={"source_draft_id": context.deterministic_draft_id, "prompt_version": prompt_version},
    ):
        try:
            provider = resolve_provider()
            suggested_event_id = _suggested_event_id(
                entity_id=entity_id,
                source_draft_id=context.deterministic_draft_id,
                provider_name=provider.provider_name,
                model_name=provider.model_name,
                prompt_version=prompt_version,
            )
            if ledger.exists(suggested_event_id):
                return {
                    "status": "duplicate",
                    "event_id": suggested_event_id,
                    "entity_id": entity_id,
                    "source_draft_id": context.deterministic_draft_id,
                }

            prompt = build_draft_prompt(context)
            suggestion = provider.suggest_draft(context=context, prompt=prompt, prompt_version=prompt_version)
            payload = {
                "entity_id": entity_id,
                "source_draft_id": context.deterministic_draft_id,
                "source_template_version": context.deterministic_template_version,
                "source_generation_mode": context.deterministic_generation_mode,
                **suggestion.model_dump(),
            }
            ledger.append(
                {
                    "event_id": suggested_event_id,
                    "event_type": EventType.AI_DRAFT_SUGGESTED.value,
                    "correlation_id": correlation_id,
                    "entity_id": entity_id,
                    "payload": payload,
                }
            )
            log.info(
                "ai_draft_suggested",
                extra={
                    "correlation_id": correlation_id,
                    "entity_id": entity_id,
                    "source_draft_id": context.deterministic_draft_id,
                    "provider_name": suggestion.provider_name,
                    "model_name": suggestion.model_name,
                },
            )
            return {
                "status": "suggested",
                "event_id": suggested_event_id,
                "entity_id": entity_id,
                "source_draft_id": context.deterministic_draft_id,
                "provider_name": suggestion.provider_name,
                "model_name": suggestion.model_name,
                "prompt_version": suggestion.prompt_version,
                "generated_at": suggestion.generated_at,
            }
        except AIProviderError as exc:
            provider_name = "unavailable"
            model_name = "unavailable"
            if exc.args and isinstance(exc.args[0], str) and exc.args[0].startswith("unsupported_provider:"):
                provider_name = exc.args[0].split(":", 1)[1]
                model_name = provider_name
            failure = AIDraftFailure(
                provider_name=provider_name,
                model_name=model_name,
                prompt_version=prompt_version,
                failed_at=iso_now(),
                failure_reason=str(exc),
            )
            failure_event_id = _failure_event_id(
                entity_id=entity_id,
                source_draft_id=context.deterministic_draft_id,
                provider_name=failure.provider_name,
                model_name=failure.model_name,
                prompt_version=prompt_version,
                failure_reason=failure.failure_reason,
            )
            if ledger.exists(failure_event_id):
                return {
                    "status": "duplicate",
                    "event_id": failure_event_id,
                    "entity_id": entity_id,
                    "source_draft_id": context.deterministic_draft_id,
                    "failure_reason": failure.failure_reason,
                }
            ledger.append(
                {
                    "event_id": failure_event_id,
                    "event_type": EventType.AI_DRAFT_GENERATION_FAILED.value,
                    "correlation_id": correlation_id,
                    "entity_id": entity_id,
                    "payload": {
                        "entity_id": entity_id,
                        "source_draft_id": context.deterministic_draft_id,
                        "source_template_version": context.deterministic_template_version,
                        "source_generation_mode": context.deterministic_generation_mode,
                        **failure.model_dump(),
                    },
                }
            )
            log.warning(
                "ai_draft_generation_failed",
                extra={
                    "correlation_id": correlation_id,
                    "entity_id": entity_id,
                    "source_draft_id": context.deterministic_draft_id,
                    "failure_reason": failure.failure_reason,
                },
            )
            return {
                "status": "failed",
                "event_id": failure_event_id,
                "entity_id": entity_id,
                "source_draft_id": context.deterministic_draft_id,
                "failure_reason": failure.failure_reason,
            }
