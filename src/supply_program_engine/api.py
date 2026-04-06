from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fastapi import Form
from fastapi.responses import RedirectResponse

from supply_program_engine import ledger
from supply_program_engine.ai import generate_draft_suggestion
from supply_program_engine.auth import (
    authenticate_operator,
    can_approve,
    can_manage_data_controls,
    can_review,
    can_run_admin_actions,
    can_send,
    clear_session_cookie,
    create_session_principal,
    issue_csrf_token,
    load_session_from_request,
    permission_context,
    set_session_cookie,
    verify_csrf_token,
)
from supply_program_engine.auth.models import SessionPrincipal
from supply_program_engine.config import settings, validate_runtime_security
from supply_program_engine.data_controls import (
    build_entity_export,
    create_subject_request,
    record_suppression,
    retention_run_once,
    update_subject_request_status,
)
from supply_program_engine.data_controls.models import (
    SubjectRequestRecord,
    SubjectRequestStatusUpdate,
    SuppressionRecord,
    iso_now,
)
from supply_program_engine.data_controls.redaction import sanitized_entity_timeline
from supply_program_engine.enrichment import run_once as enrichment_run_once
from supply_program_engine.identity import stable_entity_id
from supply_program_engine.learning import run_once as learning_run_once
from supply_program_engine.logging import generate_correlation_id, get_logger
from supply_program_engine.metrics import record_request, snapshot
from supply_program_engine.models import ApprovalDecision, Candidate, EventType, InboundReply
from supply_program_engine.observability import initialize_tracing, trace_span
from supply_program_engine.orchestrator import run_once as phase3_run_once
from supply_program_engine.outbound.orchestrator import run_once as outbound_run_once
from supply_program_engine.outbound.sender import run_once as sender_run_once
from supply_program_engine.projections import build_pipeline_state, rank_pipeline
from supply_program_engine.queue import QueueUnavailableError, TaskMessage, enqueue_task
from supply_program_engine.reply_triage import process_reply
from supply_program_engine.workers.runner import run_once as worker_run_once

log = get_logger("supply_program_engine")
templates = Jinja2Templates(directory="src/supply_program_engine/templates")


@dataclass(frozen=True)
class _AuthorizedActor:
    username: str
    roles: tuple[str, ...]
    auth_method: str


def _template_response(request: Request, name: str, **context: object) -> HTMLResponse:
    operator = getattr(request.state, "operator", None)
    permissions = asdict(permission_context(operator))
    return templates.TemplateResponse(
        request,
        name,
        {
            "request": request,
            "current_operator": operator,
            "csrf_token": issue_csrf_token(operator) if operator else None,
            **permissions,
            **context,
        },
    )


def _compute_signature(raw_body: bytes) -> str:
    secret = settings.HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def _has_valid_admin_api_key(x_admin_api_key: Optional[str]) -> bool:
    expected = settings.ADMIN_API_KEY
    return bool(expected and x_admin_api_key and hmac.compare_digest(x_admin_api_key, expected))


def _safe_next_path(path: str | None) -> str:
    if not path or not path.startswith("/") or path.startswith("//"):
        return "/ui/candidates"
    if path.startswith("/login"):
        return "/ui/candidates"
    return path


def _current_operator(request: Request) -> SessionPrincipal | None:
    return getattr(request.state, "operator", None)


def _authorized_session_actor(operator: SessionPrincipal) -> _AuthorizedActor:
    return _AuthorizedActor(
        username=operator.username,
        roles=tuple(operator.roles),
        auth_method="session",
    )


def _authorized_api_key_actor() -> _AuthorizedActor:
    return _AuthorizedActor(
        username="admin_api_key",
        roles=("admin",),
        auth_method="api_key",
    )


def _login_redirect(request: Request) -> RedirectResponse:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    safe_next = _safe_next_path(next_path)
    return RedirectResponse(url=f"/login?next={quote(safe_next, safe='/?=&')}", status_code=303)


def _require_ui_operator(request: Request, permission_check=can_review) -> SessionPrincipal | RedirectResponse:
    operator = _current_operator(request)
    if operator is None:
        return _login_redirect(request)
    if not permission_check(operator):
        raise HTTPException(status_code=403, detail="insufficient_role")
    return operator


def _require_json_operator(request: Request, permission_check=can_review) -> SessionPrincipal:
    operator = _current_operator(request)
    if operator is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    if not permission_check(operator):
        raise HTTPException(status_code=403, detail="insufficient_role")
    return operator


def _require_internal_access(
    request: Request,
    x_admin_api_key: Optional[str],
    permission_check=can_run_admin_actions,
) -> _AuthorizedActor:
    operator = _current_operator(request)
    if operator is not None and permission_check(operator):
        return _authorized_session_actor(operator)

    if _has_valid_admin_api_key(x_admin_api_key):
        return _authorized_api_key_actor()

    if operator is not None:
        raise HTTPException(status_code=403, detail="insufficient_role")

    if x_admin_api_key:
        if not settings.ADMIN_API_KEY:
            raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")
        raise HTTPException(status_code=401, detail="Invalid X-Admin-API-Key")

    raise HTTPException(status_code=401, detail="authentication_required")


def _require_csrf(request: Request, csrf_token: str) -> SessionPrincipal:
    operator = _current_operator(request)
    if operator is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    if not verify_csrf_token(csrf_token, operator):
        raise HTTPException(status_code=403, detail="invalid_csrf_token")
    return operator


def create_app() -> FastAPI:
    validate_runtime_security()
    initialize_tracing()
    app = FastAPI(title=settings.APP_NAME)

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or generate_correlation_id()
        request.state.correlation_id = cid
        request.state.operator = load_session_from_request(request)

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
    async def metrics(
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        if settings.ENV != "dev":
            _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        return snapshot()

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: str | None = None):
        operator = _current_operator(request)
        destination = _safe_next_path(next)
        if operator is not None:
            return RedirectResponse(url=destination, status_code=303)
        return _template_response(request, "login.html", next_path=destination, error=None)

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        next: str = Form("/ui/candidates"),
    ):
        destination = _safe_next_path(next)
        user = authenticate_operator(username, password)
        if user is None:
            response = _template_response(
                request,
                "login.html",
                next_path=destination,
                error="Invalid username or password.",
            )
            response.status_code = 401
            return response

        principal = create_session_principal(user)
        response = RedirectResponse(url=destination, status_code=303)
        set_session_cookie(response, principal)
        log.info("operator_login_succeeded", extra={"username": principal.username})
        return response

    @app.post("/logout")
    async def logout(request: Request, csrf_token: str = Form("")):
        _require_csrf(request, csrf_token)
        response = RedirectResponse(url="/login", status_code=303)
        clear_session_cookie(response)
        return response

    @app.post("/ingress/candidate")
    async def ingest_candidate(
        request: Request,
        x_signature: Optional[str] = Header(default=None),
    ):
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span(
            "api.candidate_ingress",
            correlation_id=cid,
            event_type=EventType.CANDIDATE_INGESTED.value,
        ):
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

            entity_id = stable_entity_id(candidate)

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
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span("api.orchestrator_run_once", correlation_id=cid, task_type="qualification_run", extra={"limit": limit}):
            result = phase3_run_once(limit=limit)
        log.info("orchestrator_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/enrichment/run-once")
    async def enrichment_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span("api.enrichment_run_once", correlation_id=cid, task_type="enrichment_run", extra={"limit": limit}):
            result = enrichment_run_once(limit=limit)
        log.info("enrichment_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/outbound/run-once")
    async def outbound_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span("api.outbound_run_once", correlation_id=cid, task_type="outbound_draft_run", extra={"limit": limit}):
            result = outbound_run_once(limit=limit)
        log.info("outbound_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/ai/drafts/suggest/{entity_id}")
    async def ai_drafts_suggest(
        entity_id: str,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span(
            "api.ai_drafts_suggest",
            correlation_id=cid,
            entity_id=entity_id,
            task_type="ai_draft_suggestion",
        ):
            try:
                result = generate_draft_suggestion(entity_id=entity_id, correlation_id=cid)
            except ValueError as exc:
                if str(exc) == "entity_not_found":
                    raise HTTPException(status_code=404, detail="Entity not found")
                raise HTTPException(status_code=400, detail=str(exc))
        log.info("ai_drafts_suggest", extra={"correlation_id": cid, "entity_id": entity_id, **result})
        return {"correlation_id": cid, **result}

    @app.post("/sender/run-once")
    async def sender_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span("api.sender_run_once", correlation_id=cid, task_type="sender_run", extra={"limit": limit}):
            result = sender_run_once(
                limit=limit,
                requested_by=actor.username,
                requested_by_roles=list(actor.roles),
            )
        log.info("sender_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/reply-triage/ingest")
    async def reply_triage_ingest(
        reply: InboundReply,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())

        with trace_span(
            "api.reply_triage_ingest",
            correlation_id=cid,
            entity_id=reply.entity_id,
            task_type="reply_triage",
        ):
            try:
                result = process_reply(reply, correlation_id=cid)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

        log.info("reply_triage_ingest", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/learning/run-once")
    async def learning_run_once_endpoint(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span("api.learning_run_once", correlation_id=cid, task_type="learning_run", extra={"limit": limit}):
            result = learning_run_once(limit=limit)
        log.info("learning_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/data-controls/suppression")
    async def data_controls_record_suppression(
        suppression: SuppressionRecord,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_manage_data_controls)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        if actor.auth_method == "session":
            suppression = suppression.model_copy(
                update={"actor": actor.username, "actor_roles": list(actor.roles)}
            )
        else:
            suppression = suppression.model_copy(
                update={
                    "actor": suppression.actor or actor.username,
                    "actor_roles": suppression.actor_roles or list(actor.roles),
                }
            )
        with trace_span(
            "api.data_controls.record_suppression",
            correlation_id=cid,
            entity_id=suppression.entity_id,
            task_type="data_controls",
            extra={"target_type": suppression.target_type, "reason": suppression.reason},
        ):
            result = record_suppression(suppression, correlation_id=cid)
        log.info("suppression_recorded", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/data-controls/subject-request")
    async def data_controls_create_subject_request(
        subject_request: SubjectRequestRecord,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_manage_data_controls)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        if actor.auth_method == "session":
            subject_request = subject_request.model_copy(
                update={"actor": actor.username, "actor_roles": list(actor.roles)}
            )
        else:
            subject_request = subject_request.model_copy(
                update={
                    "actor": subject_request.actor or actor.username,
                    "actor_roles": subject_request.actor_roles or list(actor.roles),
                }
            )
        with trace_span(
            "api.data_controls.create_subject_request",
            correlation_id=cid,
            entity_id=subject_request.entity_id,
            task_type="data_controls",
            extra={"request_type": subject_request.request_type, "target_type": subject_request.target_type},
        ):
            result = create_subject_request(subject_request, correlation_id=cid)
        log.info("subject_request_recorded", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/data-controls/subject-request/status")
    async def data_controls_update_subject_request_status(
        update: SubjectRequestStatusUpdate,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_manage_data_controls)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        if actor.auth_method == "session":
            update = update.model_copy(update={"actor": actor.username, "actor_roles": list(actor.roles)})
        else:
            update = update.model_copy(
                update={
                    "actor": update.actor or actor.username,
                    "actor_roles": update.actor_roles or list(actor.roles),
                }
            )
        with trace_span(
            "api.data_controls.update_subject_request_status",
            correlation_id=cid,
            task_type="data_controls",
            extra={"request_id": update.request_id, "status": update.status},
        ):
            try:
                result = update_subject_request_status(update, correlation_id=cid)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
        log.info("subject_request_status_updated", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/data-controls/retention/run-once")
    async def data_controls_retention_run_once(
        request: Request,
        limit: int = 50,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_manage_data_controls)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span(
            "api.data_controls.retention_run_once",
            correlation_id=cid,
            task_type="data_controls",
            extra={"limit": limit},
        ):
            result = retention_run_once(limit=limit)
        log.info("retention_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.get("/data-controls/export/entity/{entity_id}")
    async def data_controls_export_entity(
        entity_id: str,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_manage_data_controls)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        with trace_span(
            "api.data_controls.export_entity",
            correlation_id=cid,
            entity_id=entity_id,
            task_type="data_controls",
        ):
            try:
                export = build_entity_export(entity_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            export_event_id = ledger.generate_event_id(
                {
                    "event_type": EventType.DATA_EXPORT_GENERATED.value,
                    "entity_id": entity_id,
                    "correlation_id": cid,
                }
            )
            if not ledger.exists(export_event_id):
                ledger.append(
                    {
                        "event_id": export_event_id,
                        "event_type": EventType.DATA_EXPORT_GENERATED.value,
                        "correlation_id": cid,
                        "entity_id": entity_id,
                        "payload": {
                            "export_type": "entity_summary",
                            "generated_at": iso_now(),
                            "subject_request_count": len(export["subject_requests"]),
                            "suppression_count": len(export["suppression_state"]),
                            "actor": actor.username,
                            "actor_roles": list(actor.roles),
                            "auth_method": actor.auth_method,
                        },
                    }
                )
        log.info("entity_export_generated", extra={"correlation_id": cid, "entity_id": entity_id})
        return {"correlation_id": cid, **export}

    @app.post("/queue/enqueue")
    async def queue_enqueue(
        task: TaskMessage,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        queued_task = task.model_copy(update={"correlation_id": task.correlation_id or cid})

        with trace_span(
            "api.queue_enqueue",
            correlation_id=queued_task.correlation_id,
            entity_id=queued_task.entity_id,
            task_type=queued_task.task_type,
        ):
            try:
                result = enqueue_task(queued_task)
            except QueueUnavailableError as exc:
                raise HTTPException(status_code=503, detail=f"queue_unavailable:{exc}")

        log.info("task_enqueued", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/worker/run-once")
    async def worker_run_once_endpoint(
        request: Request,
        timeout_seconds: int = 0,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        _require_internal_access(request, x_admin_api_key, can_run_admin_actions)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())

        with trace_span("api.worker_run_once", correlation_id=cid, task_type="worker_run", extra={"timeout_seconds": timeout_seconds}):
            try:
                result = worker_run_once(timeout_seconds=timeout_seconds)
            except QueueUnavailableError as exc:
                raise HTTPException(status_code=503, detail=f"queue_unavailable:{exc}")

        log.info("worker_run_once", extra={"correlation_id": cid, **result})
        return {"correlation_id": cid, **result}

    @app.post("/outbound/decision")
    async def outbound_decision(
        decision: ApprovalDecision,
        request: Request,
        x_admin_api_key: Optional[str] = Header(default=None),
    ):
        actor = _require_internal_access(request, x_admin_api_key, can_approve)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())

        if not decision.reason or not decision.reason.strip():
            raise HTTPException(status_code=400, detail="Approval/rejection reason is required")

        if actor.auth_method == "session":
            decision = decision.model_copy(
                update={"actor": actor.username, "actor_roles": list(actor.roles)}
            )
        else:
            decision = decision.model_copy(
                update={
                    "actor": decision.actor or actor.username,
                    "actor_roles": decision.actor_roles or list(actor.roles),
                }
            )

        draft_event = ledger.get(decision.draft_id)
        if not draft_event or draft_event.get("event_type") != EventType.OUTBOUND_DRAFT_CREATED.value:
            raise HTTPException(status_code=404, detail="Draft not found")

        with trace_span(
            "api.outbound_decision",
            correlation_id=cid,
            entity_id=draft_event.get("entity_id"),
            event_type=decision.decision,
            extra={"draft_id": decision.draft_id, "actor": decision.actor},
        ):

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
        _require_json_operator(request)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))
        log.info("pipeline_view", extra={"correlation_id": cid, "count": len(ranked)})
        return {"correlation_id": cid, "count": len(ranked), "items": [v.model_dump() for v in ranked]}

    @app.get("/entity/{entity_id}")
    async def get_entity(entity_id: str, request: Request):
        _require_json_operator(request)
        cid = getattr(request.state, "correlation_id", generate_correlation_id())
        events = sanitized_entity_timeline(entity_id)
        if not events:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"correlation_id": cid, "entity_id": entity_id, "events": events}

    @app.get("/ui/candidates", response_class=HTMLResponse)
    async def ui_candidates(request: Request):
        gate = _require_ui_operator(request)
        if isinstance(gate, RedirectResponse):
            return gate
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))

        summary = {
            "total": len(ranked),
            "manual_review": len([x for x in ranked if x.requires_manual_review]),
            "approved": len([x for x in ranked if x.status == "approved"]),
            "sent": len([x for x in ranked if x.status == "sent"]),
        }

        return _template_response(request, "candidates.html", summary=summary)


    @app.get("/ui/candidates/table", response_class=HTMLResponse)
    async def ui_candidates_table(request: Request):
        gate = _require_ui_operator(request)
        if isinstance(gate, RedirectResponse):
            return gate
        state = build_pipeline_state()
        ranked = rank_pipeline(list(state.values()))

        return _template_response(request, "candidates_table.html", candidates=ranked)

    @app.get("/ui/discovery", response_class=HTMLResponse)
    async def ui_discovery(request: Request):
        gate = _require_ui_operator(request)
        if isinstance(gate, RedirectResponse):
            return gate
        state = build_pipeline_state()
        discovered = [
            view
            for view in rank_pipeline(list(state.values()))
            if view.source or view.discovered_via or view.source_query or view.external_id
        ]

        source_counts = Counter(view.source for view in discovered if view.source)
        region_counts = Counter(view.source_region for view in discovered if view.source_region)
        query_counts = Counter(view.source_query for view in discovered if view.source_query)

        summary = {
            "total": len(discovered),
            "sources": len(source_counts),
            "regions": len(region_counts),
            "manual_review": len([view for view in discovered if view.requires_manual_review]),
        }

        return _template_response(
            request,
            "discovery.html",
            summary=summary,
            entities=discovered,
            source_counts=source_counts.most_common(),
            region_counts=region_counts.most_common(),
            query_counts=query_counts.most_common(5),
        )


    @app.get("/ui/metrics", response_class=HTMLResponse)
    async def ui_metrics(request: Request):
        gate = _require_ui_operator(request, can_run_admin_actions)
        if isinstance(gate, RedirectResponse):
            return gate
        events = list(ledger.read())
        return _template_response(request, "metrics.html", total_events=len(events), metrics=snapshot())

    @app.get("/ui/entity/{entity_id}", response_class=HTMLResponse)
    async def ui_entity_detail(request: Request, entity_id: str):
        gate = _require_ui_operator(request)
        if isinstance(gate, RedirectResponse):
            return gate
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        events = sanitized_entity_timeline(entity_id)

        return _template_response(request, "entity_detail.html", entity=entity, events=events)

    @app.post("/ui/entity/{entity_id}/approve")
    async def ui_entity_approve(
        request: Request,
        entity_id: str,
        reason: str = Form(...),
        csrf_token: str = Form(""),
    ):
        gate = _require_ui_operator(request, can_approve)
        if isinstance(gate, RedirectResponse):
            return gate
        operator = _require_csrf(request, csrf_token)
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
            actor=operator.username,
            actor_roles=list(operator.roles),
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
        request: Request,
        entity_id: str,
        reason: str = Form(...),
        csrf_token: str = Form(""),
    ):
        gate = _require_ui_operator(request, can_approve)
        if isinstance(gate, RedirectResponse):
            return gate
        operator = _require_csrf(request, csrf_token)
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
            actor=operator.username,
            actor_roles=list(operator.roles),
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
        request: Request,
        entity_id: str,
        csrf_token: str = Form(""),
    ):
        gate = _require_ui_operator(request, can_send)
        if isinstance(gate, RedirectResponse):
            return gate
        operator = _require_csrf(request, csrf_token)
        state = build_pipeline_state()
        entity = state.get(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        if entity.status != "outbox_ready":
            raise HTTPException(status_code=400, detail="Entity is not ready to send")

        sender_run_once(
            limit=1,
            entity_id=entity_id,
            requested_by=operator.username,
            requested_by_roles=list(operator.roles),
        )

        return RedirectResponse(url=f"/ui/entity/{entity_id}", status_code=303)


    return app


app = create_app()
