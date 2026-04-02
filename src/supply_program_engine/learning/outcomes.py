from __future__ import annotations

from dataclasses import dataclass

from supply_program_engine.models import PipelineEntityView


OUTCOME_VERSION = "learning_v1"


@dataclass(frozen=True)
class OutcomeResult:
    category: str
    basis: dict[str, object]


def derive_outcome(entity: PipelineEntityView) -> OutcomeResult | None:
    if entity.unsubscribe_recorded:
        return OutcomeResult(
            category="unsubscribe",
            basis={
                "sent_at": entity.sent_at,
                "last_reply_received_at": entity.last_reply_received_at,
                "last_reply_classification": entity.last_reply_classification,
            },
        )

    if entity.lead_interested:
        return OutcomeResult(
            category="reply_interested",
            basis={
                "sent_at": entity.sent_at,
                "last_reply_received_at": entity.last_reply_received_at,
                "last_reply_classification": entity.last_reply_classification,
            },
        )

    if entity.lead_rejected:
        return OutcomeResult(
            category="reply_rejected",
            basis={
                "sent_at": entity.sent_at,
                "last_reply_received_at": entity.last_reply_received_at,
                "last_reply_classification": entity.last_reply_classification,
            },
        )

    if entity.reply_out_of_office:
        return OutcomeResult(
            category="out_of_office",
            basis={
                "sent_at": entity.sent_at,
                "last_reply_received_at": entity.last_reply_received_at,
                "last_reply_classification": entity.last_reply_classification,
            },
        )

    if entity.status == "sent" and not entity.reply_triage_status:
        return OutcomeResult(
            category="sent_no_reply",
            basis={"sent_at": entity.sent_at, "last_event_ts": entity.last_event_ts},
        )

    return None
