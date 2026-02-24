from __future__ import annotations

from asyncio import events
import hmac
import hashlib
import json
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import request

from supply_program_engine.config import settings
from supply_program_engine.logging import get_logger, generate_correlation_id
from supply_program_engine import ledger
from supply_program_engine.models import Candidate, EventType, ApprovalDecision
from supply_program_engine.orchestrator import run_once as phase3_run_once
from supply_program_engine.outbound.orchestrator import run_once as outbound_run_once
from supply_program_engine.projections import build_pipeline_state, rank_pipeline, entity_timeline

log = get_logger("supply_program_engine")


def _stable_entity_id(candidate: Candidate) -> str:
    basis = (candidate.website or "").strip().lower()
    if not basis:
        basis = f"{candidate.company_name.strip().lower()}|{candidate.location.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _compute_signature(raw_body: bytes) -> str:
    secret = settings.HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or generate_correlation_id()
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        cid = getattr(request.state, "correlation_id", "unknown")
        log.error("unhandled_exception", extra={"correlation_id": cid})
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "correlation_id": cid},
        )

    @app.post("/ingress/candidate")
    async def ingest_candidate(
        request: Request,
        x_signature: Optional[str] = Header(default=None),
    ):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        raw = await request.body()

        # Enforce signature outside dev
        if settings.ENV != "dev":
            if not x_signature:
                raise HTTPException(status_code=401, detail="Missing X-Signature")
            expected = _compute_signature(raw)
            if not hmac.compare_digest(x_signature, expected):
                raise HTTPException(status_code=401, detail="Invalid X-Signature")

        try:
            payload_obj = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        candidate = Candidate(**payload_obj)
        event_payload = candidate.model_dump()

        event_id = ledger.generate_event_id(
            {"event_type": EventType.CANDIDATE_INGESTED.value, "candidate": event_payload}
        )

        if ledger.exists(event_id):
            log.info("candidate_ingest_duplicate", extra={"correlation_id": cid, "event_id": event_id})
            return {"status": "duplicate", "event_id": event_id, "correlation_id": cid}

        entity_id = _stable_entity_id(candidate)

        stored = ledger.append(
            {
                "event_id": event_id,
                "event_type": EventType.CANDIDATE_INGESTED.value,
                "correlation_id": cid,
                "entity_id": entity_id,
                "payload": event_payload,
            }
        )

        log.info("candidate_ingested", extra={"correlation_id": cid, "event_id": event_id, "entity_id": entity_id})

        return {
            "status": "ingested",
            "event_id": stored["event_id"],
            "entity_id": stored["entity_id"],
            "correlation_id": cid,
        }

    # Phase 3 orchestrator endpoint
    @app.post("/orchestrator/run-once")
    async def orchestrator_run_once(request: Request, limit: int = 50):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        result = phase3_run_once(limit=limit)
        log.info("orchestrator_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    # Phase 4 outbound draft generation
    @app.post("/outbound/run-once")
    async def outbound_run_once_endpoint(request: Request, limit: int = 50):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        result = outbound_run_once(limit=limit)
        log.info("outbound_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    # Phase 4 approval decision (approve/reject)
    @app.post("/outbound/decision")
    async def outbound_decision(decision: ApprovalDecision, request: Request):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())

        draft_event = ledger.get(decision.draft_id)
        if not draft_event or draft_event.get("event_type") != EventType.OUTBOUND_DRAFT_CREATED.value:
            raise HTTPException(status_code=404, detail="Draft not found")

        decision_event_type = (
            EventType.OUTBOUND_APPROVED.value
            if decision.decision == "approved"
            else EventType.OUTBOUND_REJECTED.value
        )

        decision_event_id = ledger.generate_event_id(
            {
                "event_type": decision_event_type,
                "draft_id": decision.draft_id,
                "actor": decision.actor,
                "reason": decision.reason or "",
            }
        )

        if ledger.exists(decision_event_id):
            return {"status": "duplicate", "event_id": decision_event_id, "correlation_id": cid}

        stored = ledger.append(
            {
                "event_id": decision_event_id,
                "event_type": decision_event_type,
                "correlation_id": cid,
                "entity_id": draft_event.get("entity_id"),
                "payload": decision.model_dump(),
            }
        )

        log.info(
            "outbound_decision_recorded",
            extra={
                "correlation_id": cid,
                "draft_id": decision.draft_id,
                "decision": decision.decision,
                "actor": decision.actor,
            },
        )

        return {"status": "recorded", "event_id": stored["event_id"], "correlation_id": cid}

    @app.get("/pipeline")
    async def get_pipeline(request: Request):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))
        log.info("pipeline_view", extra={"correlation_id": cid, "count": len(ranked)})
        return {"correlation_id": cid, "count": len(ranked), "items": [v.model_dump() for v in ranked]}


    @app.get("/entity/{entity_id}")
    async def get_entity(entity_id: str, request: Request):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        events = entity_timeline(entity_id)
        if not events:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"correlation_id": cid, "entity_id": entity_id, "events": events}

    return app


app = create_app()