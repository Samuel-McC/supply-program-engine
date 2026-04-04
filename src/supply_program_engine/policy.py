from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.models import EventType, PipelineEntityView


POLICY_VERSION = "send_policy_v1"


@dataclass(frozen=True)
class SuppressionRules:
    suppressed_entities: frozenset[str]
    suppressed_domains: frozenset[str]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    blocked_reasons: tuple[str, ...]
    policy_version: str = POLICY_VERSION


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _parse_csv(value: str) -> frozenset[str]:
    return frozenset(part.strip().lower() for part in value.split(",") if part.strip())


def _extract_domain(website: str | None) -> str | None:
    if not website:
        return None

    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = parsed.netloc or parsed.path
    host = host.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def suppression_rules() -> SuppressionRules:
    return SuppressionRules(
        suppressed_entities=_parse_csv(settings.SUPPRESSED_ENTITIES),
        suppressed_domains=_parse_csv(settings.SUPPRESSED_DOMAINS),
    )


def evaluate_send_policy(entity_id: str, entity: PipelineEntityView) -> PolicyDecision:
    blocked_reasons: list[str] = []
    rules = suppression_rules()

    if entity.requires_manual_review:
        blocked_reasons.append("requires_manual_review")

    if entity.risk_score > settings.SEND_POLICY_RISK_THRESHOLD:
        blocked_reasons.append(
            f"risk_score_above_threshold:{entity.risk_score}>{settings.SEND_POLICY_RISK_THRESHOLD}"
        )

    normalized_entity_id = _normalize(entity_id)
    normalized_company_name = _normalize(entity.company_name)
    if (
        normalized_entity_id in rules.suppressed_entities
        or normalized_company_name in rules.suppressed_entities
    ):
        blocked_reasons.append("entity_suppressed")

    domain = _extract_domain(entity.website)
    if domain and domain in rules.suppressed_domains:
        blocked_reasons.append(f"domain_suppressed:{domain}")

    if entity.marketing_suppressed or entity.unsubscribe_recorded:
        blocked_reasons.append(
            f"marketing_suppressed:{entity.marketing_suppression_reason or 'direct_marketing_objected'}"
        )

    if ledger.any_event_for_entity(entity_id, EventType.OUTBOUND_SENT.value):
        blocked_reasons.append("already_sent")

    return PolicyDecision(
        allowed=not blocked_reasons,
        blocked_reasons=tuple(blocked_reasons),
    )
