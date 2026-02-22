from __future__ import annotations

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
from supply_program_engine.models import Candidate, EventType
from supply_program_engine.orchestrator import run_once

log = get_logger("supply_program_engine")


def _stable_entity_id(candidate: Candidate) -> str:
    """
    Stable ID for a company entity. Prefer website; fallback to name+location.
    """
    basis = (candidate.website or "").strip().lower()
    if not basis:
        basis = f"{candidate.company_name.strip().lower()}|{candidate.location.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _compute_signature(raw_body: bytes) -> str:
    """
    HMAC-SHA256 over raw request bytes. Returned as hex string.
    """
    secret = settings.HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        # Accept inbound correlation id, otherwise create one
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
        # signature can be optional in dev; enforce in prod by env check below
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

        # Parse JSON into Candidate
        try:
            payload_obj = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        candidate = Candidate(**payload_obj)

        # Compute deterministic event id for idempotent ingest
        event_payload = candidate.model_dump()
        event_id = ledger.generate_event_id(
            {
                "event_type": EventType.CANDIDATE_INGESTED.value,
                "candidate": event_payload,
            }
        )

        @app.post("/orchestrator/run-once")
        async def orchestrator_run_once(request: Request, limit: int = 50):
            cid = getattr(request.state, "correlation_id", generate_correlation_id())
            result = run_once(limit=limit)
            log.info("orchestrator_run_once", extra={"correlation_id": cid, **result})
            return {"correlation_id": cid, **result}

        # idempotent response
        if ledger.exists(event_id):
            log.info(
                "candidate_ingest_duplicate",
                extra={"correlation_id": cid, "event_id": event_id},
            )
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

        log.info(
            "candidate_ingested",
            extra={"correlation_id": cid, "event_id": event_id, "entity_id": entity_id},
        )

        return {
            "status": "ingested",
            "event_id": stored["event_id"],
            "entity_id": stored["entity_id"],
            "correlation_id": cid,
        }

    return app


app = create_app()