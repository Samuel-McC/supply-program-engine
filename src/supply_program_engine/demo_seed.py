from __future__ import annotations

import json
from contextlib import contextmanager

from supply_program_engine import ledger
from supply_program_engine.enrichment.fetch import FetchedWebsite
from supply_program_engine.enrichment.runner import run_once as enrichment_run_once
from supply_program_engine.identity import stable_entity_id
from supply_program_engine.learning.runner import run_once as learning_run_once
from supply_program_engine.models import ApprovalDecision, Candidate, EventType, InboundReply
from supply_program_engine.orchestrator import run_once as qualification_run_once
from supply_program_engine.outbound.orchestrator import run_once as outbound_run_once
from supply_program_engine.outbound.sender import run_once as sender_run_once
from supply_program_engine.projections import build_pipeline_state
from supply_program_engine.reply_triage.runner import process_reply

DEMO_LIMIT = 200
DEMO_OPERATOR = "demo.operator"
DEMO_APPROVAL_REASON = "Demo approval for seeded workflow walkthrough."

DEMO_CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        company_name="Atlas Industrial Lumber",
        website="https://atlas-industrial.example",
        location="Houston, TX",
        source="mock_directory",
        discovered_via="industrial distributor",
        external_id="atlas-001",
        source_query="industrial lumber distributor",
        source_region="Texas",
        source_confidence=0.96,
    ),
    Candidate(
        company_name="Beacon Formwork Supply",
        website="https://beacon-formwork.example",
        location="Dallas, TX",
        source="mock_directory",
        discovered_via="regional building supplier",
        external_id="beacon-001",
        source_query="formwork building supplier",
        source_region="Texas",
        source_confidence=0.93,
    ),
    Candidate(
        company_name="Cedar Ridge Distributor",
        website=None,
        location="Birmingham, AL",
        source="manual",
        discovered_via="lumber wholesaler referral",
        external_id="cedar-001",
        source_query="manual referral",
        source_region="Alabama",
        source_confidence=0.9,
    ),
)

DEMO_WEBSITE_FIXTURES: dict[str, FetchedWebsite] = {
    "https://atlas-industrial.example": FetchedWebsite(
        final_url="https://atlas-industrial.example",
        status_code=200,
        title="Atlas Industrial Lumber Distributor",
        meta_description="Commercial distributor of film-faced panels and industrial building materials.",
        html="""
        <html>
          <head>
            <title>Atlas Industrial Lumber Distributor</title>
            <meta name="description" content="Commercial distributor of film-faced panels and industrial building materials.">
          </head>
          <body>
            <a href="/contact">Contact us</a>
            <p>Industrial supply, procurement support, distributor inventory and contractor projects.</p>
          </body>
        </html>
        """,
    ),
    "https://beacon-formwork.example": FetchedWebsite(
        final_url="https://beacon-formwork.example",
        status_code=200,
        title="Beacon Formwork Supply",
        meta_description="Regional building supply partner for concrete contractors and formwork crews.",
        html="""
        <html>
          <head>
            <title>Beacon Formwork Supply</title>
            <meta name="description" content="Regional building supply partner for concrete contractors and formwork crews.">
          </head>
          <body>
            <a href="/contact">Get in touch</a>
            <p>Building supply programs for construction teams, contractor projects and procurement leads.</p>
          </body>
        </html>
        """,
    ),
}

DEMO_REPLIES: tuple[InboundReply, ...] = (
    InboundReply(
        entity_id=stable_entity_id(DEMO_CANDIDATES[0]),
        reply_text="We are interested. Please send pricing and panel specs.",
        received_at="2026-04-02T09:00:00+00:00",
    ),
    InboundReply(
        entity_id=stable_entity_id(DEMO_CANDIDATES[1]),
        reply_text="Please unsubscribe us from future outreach.",
        received_at="2026-04-02T09:05:00+00:00",
    ),
)


@contextmanager
def _demo_enrichment_fixtures():
    from supply_program_engine.enrichment import runner as enrichment_runner

    original_fetch = enrichment_runner.fetch_public_website
    enrichment_runner.fetch_public_website = lambda url: DEMO_WEBSITE_FIXTURES[url]
    try:
        yield
    finally:
        enrichment_runner.fetch_public_website = original_fetch


@contextmanager
def _demo_sender_settings():
    from supply_program_engine.config import settings

    original_provider = settings.OUTBOUND_PROVIDER
    original_dry_run = settings.OUTBOUND_DRY_RUN

    settings.OUTBOUND_PROVIDER = "mock"
    settings.OUTBOUND_DRY_RUN = True
    try:
        yield
    finally:
        settings.OUTBOUND_PROVIDER = original_provider
        settings.OUTBOUND_DRY_RUN = original_dry_run


def _seed_candidates() -> list[str]:
    entity_ids: list[str] = []

    for index, candidate in enumerate(DEMO_CANDIDATES, start=1):
        payload = candidate.model_dump()
        event_id = ledger.generate_event_id(
            {"event_type": EventType.CANDIDATE_INGESTED.value, "candidate": payload}
        )
        entity_id = stable_entity_id(candidate)
        entity_ids.append(entity_id)

        if ledger.exists(event_id):
            continue

        ledger.append(
            {
                "event_id": event_id,
                "event_type": EventType.CANDIDATE_INGESTED.value,
                "correlation_id": f"demo-seed-{index}",
                "entity_id": entity_id,
                "payload": payload,
            }
        )

    return entity_ids


def _approve_seeded_drafts(entity_ids: list[str]) -> dict[str, int]:
    approvals = 0
    outbox_ready = 0
    state = build_pipeline_state()

    for entity_id in entity_ids:
        entity = state.get(entity_id)
        if entity is None or not entity.draft_id:
            continue

        decision = ApprovalDecision(
            draft_id=entity.draft_id,
            decision="approved",
            actor=DEMO_OPERATOR,
            reason=DEMO_APPROVAL_REASON,
        )
        decision_event_id = ledger.generate_event_id(
            {
                "event_type": EventType.OUTBOUND_APPROVED.value,
                "draft_id": decision.draft_id,
                "actor": decision.actor,
                "reason": decision.reason,
            }
        )
        if not ledger.exists(decision_event_id):
            ledger.append(
                {
                    "event_id": decision_event_id,
                    "event_type": EventType.OUTBOUND_APPROVED.value,
                    "correlation_id": "demo-seed-approval",
                    "entity_id": entity_id,
                    "payload": decision.model_dump(),
                }
            )
            approvals += 1

        outbox_event_id = ledger.generate_event_id(
            {
                "event_type": EventType.OUTBOX_READY.value,
                "draft_id": decision.draft_id,
                "entity_id": entity_id,
            }
        )
        if not ledger.exists(outbox_event_id):
            ledger.append(
                {
                    "event_id": outbox_event_id,
                    "event_type": EventType.OUTBOX_READY.value,
                    "correlation_id": "demo-seed-approval",
                    "entity_id": entity_id,
                    "payload": {
                        "draft_id": decision.draft_id,
                        "channel": "email",
                        "status": "ready",
                    },
                }
            )
            outbox_ready += 1

    return {"approvals": approvals, "outbox_ready": outbox_ready}


def _should_run_sender(entity_ids: list[str]) -> bool:
    state = build_pipeline_state()
    return any(state.get(entity_id) and state[entity_id].status == "outbox_ready" for entity_id in entity_ids)


def run_demo_seed() -> dict[str, object]:
    entity_ids = _seed_candidates()

    with _demo_enrichment_fixtures():
        enrichment_result = enrichment_run_once(limit=DEMO_LIMIT)

    qualification_result = qualification_run_once(limit=DEMO_LIMIT)
    outbound_result = outbound_run_once(limit=DEMO_LIMIT)
    approval_result = _approve_seeded_drafts(entity_ids)

    with _demo_sender_settings():
        sender_result = sender_run_once(limit=DEMO_LIMIT) if _should_run_sender(entity_ids) else {
            "processed": 0,
            "emitted": 0,
            "blocked": 0,
            "failed": 0,
            "skipped_duplicates": 0,
            "skipped_unapproved": 0,
        }

    reply_results = [process_reply(reply, correlation_id="demo-seed-reply") for reply in DEMO_REPLIES]
    learning_result = learning_run_once(limit=DEMO_LIMIT)

    state = build_pipeline_state()
    entities_summary = []
    for candidate in DEMO_CANDIDATES:
        entity = state[stable_entity_id(candidate)]
        entities_summary.append(
            {
                "entity_id": entity.entity_id,
                "company_name": entity.company_name,
                "status": entity.status,
                "segment": entity.segment,
                "provider_status": entity.provider_status,
                "latest_outcome": entity.latest_outcome,
                "blocked_reasons": entity.blocked_reasons,
            }
        )

    return {
        "entity_count": len(entity_ids),
        "entity_ids": entity_ids,
        "steps": {
            "enrichment": enrichment_result,
            "qualification": qualification_result,
            "outbound": outbound_result,
            "approval": approval_result,
            "sender": sender_result,
            "reply_triage": reply_results,
            "learning": learning_result,
        },
        "entities": entities_summary,
        "ui_urls": {
            "candidates": "/ui/candidates",
            "discovery": "/ui/discovery",
        },
    }


def main() -> int:
    print(json.dumps(run_demo_seed(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
