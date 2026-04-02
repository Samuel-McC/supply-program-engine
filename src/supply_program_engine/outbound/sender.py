from __future__ import annotations

from datetime import datetime, timezone

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.logging import get_logger
from supply_program_engine.models import EventType
from supply_program_engine.observability import trace_span
from supply_program_engine.outbound.providers import get_provider
from supply_program_engine.outbound.providers.base import ProviderSendRequest
from supply_program_engine.policy import evaluate_send_policy
from supply_program_engine.projections import build_pipeline_state

log = get_logger("supply_program_engine")


def _draft_event(entity_draft_id: str | None) -> dict | None:
    if not entity_draft_id:
        return None
    return ledger.get(entity_draft_id)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_once(limit: int = 50) -> dict:
    """
    Provider-backed sender.

    Looks for outbox_ready events, enforces policy/idempotency, emits provider
    lifecycle events, and then emits outbound_sent once accepted.
    """
    processed = 0
    emitted = 0
    blocked = 0
    failed = 0
    skipped_duplicates = 0
    skipped_unapproved = 0
    provider = get_provider()

    with trace_span("runner.sender.batch", task_type="sender_run", extra={"limit": limit}):
        for rec in ledger.read():
            if processed >= limit:
                break

            if rec.get("event_type") != EventType.OUTBOX_READY.value:
                continue

            processed += 1

            cid = rec.get("correlation_id", "unknown")
            entity_id = rec.get("entity_id", "unknown")
            payload = rec.get("payload") or {}
            draft_id = payload.get("draft_id")

            with trace_span(
                "runner.sender.entity",
                correlation_id=cid,
                entity_id=entity_id,
                event_type=EventType.OUTBOX_READY.value,
                extra={"draft_id": draft_id},
            ):
                if not draft_id:
                    skipped_unapproved += 1
                    continue

                entity = build_pipeline_state().get(entity_id)
                if entity is None:
                    skipped_unapproved += 1
                    continue

                draft_event = _draft_event(entity.draft_id)
                draft_payload = (draft_event or {}).get("payload") or {}
                if not draft_payload:
                    skipped_unapproved += 1
                    continue

                decision = evaluate_send_policy(entity_id=entity_id, entity=entity)
                if not decision.allowed:
                    blocked_event_id = ledger.generate_event_id(
                        {
                            "event_type": EventType.OUTBOUND_SEND_BLOCKED.value,
                            "entity_id": entity_id,
                            "draft_id": draft_id,
                            "blocked_reasons": decision.blocked_reasons,
                            "policy_version": decision.policy_version,
                        }
                    )

                    if ledger.exists(blocked_event_id):
                        skipped_duplicates += 1
                        continue

                    ledger.append(
                        {
                            "event_id": blocked_event_id,
                            "event_type": EventType.OUTBOUND_SEND_BLOCKED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "draft_id": draft_id,
                                "channel": payload.get("channel", "email"),
                                "status": "blocked",
                                "blocked_reasons": decision.blocked_reasons,
                                "policy_version": decision.policy_version,
                            },
                        }
                    )

                    blocked += 1
                    log.info(
                        "outbound_send_blocked",
                        extra={
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "draft_id": draft_id,
                            "blocked_reasons": decision.blocked_reasons,
                        },
                    )
                    continue

                requested_at = _iso_now()
                requested_event_id = ledger.generate_event_id(
                    {
                        "event_type": EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value,
                        "entity_id": entity_id,
                        "draft_id": draft_id,
                        "provider_name": provider.name,
                    }
                )

                if not ledger.exists(requested_event_id):
                    ledger.append(
                        {
                            "event_id": requested_event_id,
                            "event_type": EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "draft_id": draft_id,
                                "provider_name": provider.name,
                                "requested_at": requested_at,
                                "status": "requested",
                            },
                        }
                    )

                with trace_span(
                    "runner.sender.provider_send",
                    correlation_id=cid,
                    entity_id=entity_id,
                    provider_name=provider.name,
                    extra={"draft_id": draft_id},
                ):
                    provider_result = provider.send(
                        ProviderSendRequest(
                            draft_id=draft_id,
                            entity_id=entity_id,
                            to_hint=draft_payload.get("to_hint"),
                            subject=draft_payload.get("subject", ""),
                            body=draft_payload.get("body", ""),
                            from_email=settings.OUTBOUND_FROM_EMAIL,
                            from_name=settings.OUTBOUND_FROM_NAME,
                            reply_to_email=settings.OUTBOUND_REPLY_TO_EMAIL,
                        )
                    )

                if not provider_result.accepted:
                    failed_event_id = ledger.generate_event_id(
                        {
                            "event_type": EventType.OUTBOUND_PROVIDER_SEND_FAILED.value,
                            "entity_id": entity_id,
                            "draft_id": draft_id,
                            "provider_name": provider_result.provider_name,
                            "failure_reason": provider_result.failure_reason,
                        }
                    )

                    if ledger.exists(failed_event_id):
                        skipped_duplicates += 1
                        continue

                    ledger.append(
                        {
                            "event_id": failed_event_id,
                            "event_type": EventType.OUTBOUND_PROVIDER_SEND_FAILED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "draft_id": draft_id,
                                "provider_name": provider_result.provider_name,
                                "provider_message_id": provider_result.provider_message_id,
                                "failed_at": _iso_now(),
                                "status": provider_result.status,
                                "failure_reason": provider_result.failure_reason,
                            },
                        }
                    )

                    failed += 1
                    log.warning(
                        "outbound_provider_send_failed",
                        extra={
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "draft_id": draft_id,
                            "provider_name": provider_result.provider_name,
                            "failure_reason": provider_result.failure_reason,
                        },
                    )
                    continue

                accepted_event_id = ledger.generate_event_id(
                    {
                        "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
                        "entity_id": entity_id,
                        "draft_id": draft_id,
                        "provider_name": provider_result.provider_name,
                        "provider_message_id": provider_result.provider_message_id,
                    }
                )

                if not ledger.exists(accepted_event_id):
                    ledger.append(
                        {
                            "event_id": accepted_event_id,
                            "event_type": EventType.OUTBOUND_PROVIDER_SEND_ACCEPTED.value,
                            "correlation_id": cid,
                            "entity_id": entity_id,
                            "payload": {
                                "draft_id": draft_id,
                                "provider_name": provider_result.provider_name,
                                "provider_message_id": provider_result.provider_message_id,
                                "accepted_at": _iso_now(),
                                "status": provider_result.status,
                            },
                        }
                    )

                sent_event_id = ledger.generate_event_id(
                    {
                        "event_type": EventType.OUTBOUND_SENT.value,
                        "entity_id": entity_id,
                        "draft_id": draft_id,
                    }
                )

                if ledger.exists(sent_event_id):
                    skipped_duplicates += 1
                    continue

                stored = ledger.append(
                    {
                        "event_id": sent_event_id,
                        "event_type": EventType.OUTBOUND_SENT.value,
                        "correlation_id": cid,
                        "entity_id": entity_id,
                        "payload": {
                            "draft_id": draft_id,
                            "channel": payload.get("channel", "email"),
                            "status": "sent",
                            "provider_name": provider_result.provider_name,
                            "provider_message_id": provider_result.provider_message_id,
                        },
                    }
                )

                emitted += 1
                log.info(
                    "outbound_sent",
                    extra={"correlation_id": cid, "entity_id": entity_id, "event_id": stored["event_id"]},
                )

    return {
        "processed": processed,
        "emitted": emitted,
        "blocked": blocked,
        "failed": failed,
        "skipped_duplicates": skipped_duplicates,
        "skipped_unapproved": skipped_unapproved,
    }
