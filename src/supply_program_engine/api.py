from __future__ import annotations

import hashlib
import hmac
import json
import time
from tracemalloc import start
from typing import Optional
from urllib import request, response

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from fastapi import Form
from fastapi.responses import RedirectResponse
from supply_program_engine.models import ApprovalDecision

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.metrics import record_request, snapshot
from supply_program_engine.models import ApprovalDecision, Candidate, EventType
from supply_program_engine.orchestrator import run_once as phase3_run_once
from supply_program_engine.outbound.orchestrator import run_once as outbound_run_once
from supply_program_engine.outbound.sender import run_once as sender_run_once
from supply_program_engine.projections import build_pipeline_state, entity_timeline, rank_pipeline

log = get_logger("supply_program_engine")
templates = Jinja2Templates(directory="src/supply_program_engine/templates")


def _stable_entity_id(candidate: Candidate) -> str:
    """
    Stable identity preference:
    1. website
    2. external_id + source
    3. company_name + location
    """
    if candidate.website and candidate.website.strip():
        basis = candidate.website.strip().lower()
    elif candidate.external_id and candidate.source:
        basis = f"{candidate.source.strip().lower()}|{candidate.external_id.strip().lower()}"
    else:
        basis = f"{candidate.company_name.strip().lower()}|{candidate.location.strip().lower()}"

    return hashlib.sha256(basis.encode("utf-8")).hexdigest()



def _compute_signature(raw_body: bytes) -> str:
    secret = settings.HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def _require_admin_api_key(x_admin_api_key: Optional[str]) -> None:
    if settings.ENV == "dev":
        return

    expected = settings.ADMIN_API_KEY
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")

    if not x_admin_api_key:
        raise HTTPException(status_code=401, detail="Missing X-Admin-API-Key")

    if not hmac.compare_digest(x_admin_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid X-Admin-API-Key")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or generate_correlation_id()
        request.state.correlation_id = cid

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        try:
            record_request(str(request.url.path), float(duration))
        except Exception as exc:
            log.warning(
                "metrics_record_failure",
                extra={
                    "path": str(request.url.path),
                    "error": str(exc),
                },
            )


        response.headers["x-correlation-id"] = cid
        response.headers["x-response-time-ms"] = str(round(duration * 1000, 2))
        return response


    #@app.exception_handler(Exception)
    #async def unhandled_exception_handler(request: Request, exc: Exception):
        #cid = getattr(request.state, "correlation_id", "unknown")
        #log.error("unhandled_exception", extra={"correlation_id": cid})
        #return JSONResponse(
            #status_code=500,
            #content={"error": "internal_error", "correlation_id": cid},
        #)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.APP_NAME, "env": settings.ENV}

    @app.get("/ready")
    async def ready():
        if settings.LEDGER_BACKEND == "db" and not settings.DATABASE_URL:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured for db backend")
        return {"status": "ready", "ledger_backend": settings.LEDGER_BACKEND}

    @app.get("/metrics")
    async def metrics():
        return snapshot()

    @app.post("/ingress/candidate")
    async def ingest_candidate(
        request: Request,
        x_signature: Optional[str] = Header(default=None),
    ):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        raw = await request.body()

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

    @app.post("/orchestrator/run-once")
    async def orchestrator_run_once(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_admin_api_key(x_admin_api_key)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        result = phase3_run_once(limit=limit)
        log.info("orchestrator_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/outbound/run-once")
    async def outbound_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_admin_api_key(x_admin_api_key)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        result = outbound_run_once(limit=limit)
        log.info("outbound_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/sender/run-once")
    async def sender_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_admin_api_key(x_admin_api_key)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        result = sender_run_once(limit=limit)
        log.info("sender_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/outbound/decision")
    async def outbound_decision(
        decision: ApprovalDecision,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_admin_api_key(x_admin_api_key)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())

        if not decision.reason or not decision.reason.strip():
            raise HTTPException(status_code=400, detail="Approval/rejection reason is required")

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

        if decision.decision == "approved":
            outbox_event_id = ledger.generate_event_id(
                {
                    "event_type": EventType.OUTBOX_READY.value,
                    "draft_id": decision.draft_id,
                    "entity_id": draft_event.get("entity_id"),
                }
            )

            if not ledger.exists(outbox_event_id):
                ledger.append(
                    {
                        "event_id": outbox_event_id,
                        "event_type": EventType.OUTBOX_READY.value,
                        "correlation_id": cid,
                        "entity_id": draft_event.get("entity_id"),
                        "payload": {
                            "draft_id": decision.draft_id,
                            "channel": "email",
                            "status": "ready",
                        },
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

    @app.get("/ui/candidates", response_class=HTMLResponse)
    async def ui_candidates(request: Request):
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))

        summary = {
            "total": len(ranked),
            "manual_review": len([x for x in ranked if x.requires_manual_review]),
            "approved": len([x for x in ranked if x.status == "approved"]),
            "sent": len([x for x in ranked if x.status == "sent"]),
        }

        return templates.TemplateResponse(
            "candidates.html",
            {
                "request": request,
                "summary": summary,
            },
    )


    @app.get("/ui/candidates/table", response_class=HTMLResponse)
    async def ui_candidates_table(request: Request):
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))

        return templates.TemplateResponse(
            "candidates_table.html",
            {   
                "request": request,
                "candidates": ranked,
            },
    )


    @app.get("/ui/metrics", response_class=HTMLResponse)
    async def ui_metrics(request: Request):
        events = list(ledger.read())
        return templates.TemplateResponse(
            "metrics.html",
            {
                "request": request,
                "total_events": len(events),
                "metrics": snapshot(),
            },
        )

    @app.get("/ui/entity/{entity_id}", response_class=HTMLResponse)
    async def ui_entity_detail(request: Request, entity_id: str):
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        events = entity_timeline(entity_id)

        return templates.TemplateResponse(
            "entity_detail.html",
            {
                "request": request,
                "entity": entity,
                "events": events,
            },
        )

    @app.post("/ui/entity/{entity_id}/approve")
    async def ui_entity_approve(
        entity_id: str,
        actor: str = Form(...),
        reason: str = Form(...),
    ):
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        if not entity.draft_id:
            raise HTTPException(status_code=400, detail="No draft available")

        if not reason.strip():
            raise HTTPException(status_code=400, detail="Approval reason is required")

        decision = ApprovalDecision(
            draft_id=entity.draft_id,
            decision="approved",
            actor=actor,
            reason=reason,
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
                    "correlation_id": "ui-action",
                    "entity_id": entity_id,
                    "payload": decision.model_dump(),
                }
            )

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
                    "correlation_id": "ui-action",
                    "entity_id": entity_id,
                    "payload": {
                        "draft_id": decision.draft_id,
                        "channel": "email",
                        "status": "ready",
                    },
                }
            )

        return RedirectResponse(url=f"/ui/entity/{entity_id}", status_code=303)

    @app.post("/ui/entity/{entity_id}/reject")
    async def ui_entity_reject(
        entity_id: str,
        actor: str = Form(...),
        reason: str = Form(...),
    ):
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        if not entity.draft_id:
            raise HTTPException(status_code=400, detail="No draft available")

        if not reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required")

        decision = ApprovalDecision(
            draft_id=entity.draft_id,
            decision="rejected",
            actor=actor,
            reason=reason,
        )

        decision_event_id = ledger.generate_event_id(
            {
                "event_type": EventType.OUTBOUND_REJECTED.value,
                "draft_id": decision.draft_id,
                "actor": decision.actor,
                "reason": decision.reason,
            }
        )

        if not ledger.exists(decision_event_id):
            ledger.append(
                {
                    "event_id": decision_event_id,
                    "event_type": EventType.OUTBOUND_REJECTED.value,
                    "correlation_id": "ui-action",
                    "entity_id": entity_id,
                    "payload": decision.model_dump(),
                }
            )

        return RedirectResponse(url=f"/ui/entity/{entity_id}", status_code=303)
    

    @app.post("/ui/entity/{entity_id}/send-now")
    async def ui_entity_send_now(
        entity_id: str,
        actor: str = Form(...),
    ):
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        if entity.status != "outbox_ready":
            raise HTTPException(status_code=400, detail="Entity is not ready to send")

        sender_run_once(limit=50)

        return RedirectResponse(url=f"/ui/entity/{entity_id}", status_code=303)


    return app


app = create_app()
