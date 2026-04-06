import json
import re

from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.auth.security import hash_password
from supply_program_engine.config import settings
from supply_program_engine.models import EventType


def _operator_users_json(*users: dict[str, object]) -> str:
    payload = []
    for user in users:
        payload.append(
            {
                "username": user["username"],
                "display_name": user.get("display_name", user["username"]),
                "password_hash": hash_password(str(user["password"])),
                "roles": list(user["roles"]),
            }
        )
    return json.dumps(payload)


def _client(tmp_path, monkeypatch, *, operator_users_json: str | None = None) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "SESSION_SECRET", "test-session-secret")
    monkeypatch.setattr(settings, "HMAC_SECRET", "test-hmac-secret")
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "OPERATOR_USERS_JSON", operator_users_json or "")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setattr(settings, "OUTBOUND_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OUTBOUND_DRY_RUN", True)
    return TestClient(create_app())


def _login(
    client: TestClient,
    *,
    username: str = "demo-admin",
    password: str = "dev-password",
    next_path: str = "/ui/candidates",
):
    return client.post(
        "/login",
        data={"username": username, "password": password, "next": next_path},
        follow_redirects=False,
    )


def _extract_csrf_token(body: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None
    return match.group(1)


def _seed_candidate(entity_id: str = "entity-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-candidate",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Acme Panels",
                "website": "https://acme-panels.example",
                "location": "TX",
                "source": "manual",
                "discovered_via": "industrial distributor",
            },
        }
    )


def _seed_draft(entity_id: str = "entity-1", draft_id: str = "draft-1") -> None:
    ledger.append(
        {
            "event_id": draft_id,
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "entity_id": entity_id,
                "segment": "industrial_distributor",
                "subject": "Supply program",
                "body": "Hello",
                "to_hint": "buyer@example.com",
                "template_version": "v1",
                "generation_mode": "deterministic",
            },
        }
    )


def _seed_outbox_ready(entity_id: str = "entity-1", draft_id: str = "draft-1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-outbox-ready",
            "event_type": EventType.OUTBOX_READY.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": draft_id,
                "channel": "email",
                "status": "ready",
            },
        }
    )


def test_unauthenticated_ui_routes_redirect_and_json_routes_require_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _seed_candidate()

    ui_response = client.get("/ui/candidates", follow_redirects=False)
    api_response = client.get("/pipeline", follow_redirects=False)

    assert ui_response.status_code == 303
    assert ui_response.headers["location"].startswith("/login?next=/ui/candidates")
    assert api_response.status_code == 401
    assert api_response.json()["detail"] == "authentication_required"


def test_create_app_fails_closed_for_weak_non_dev_security_config(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "HMAC_SECRET", "dev-secret")
    monkeypatch.setattr(settings, "SESSION_SECRET", "dev-secret")
    monkeypatch.setattr(settings, "OPERATOR_USERS_JSON", "")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)

    try:
        create_app()
    except RuntimeError as exc:
        message = str(exc)
        assert "HMAC_SECRET" in message
        assert "SESSION_SECRET" in message
        assert "ADMIN_API_KEY" in message or "OPERATOR_USERS_JSON" in message
    else:
        raise AssertionError("Expected create_app() to fail closed outside dev")


def test_login_and_logout_manage_operator_session(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    login = _login(client)

    assert login.status_code == 303
    assert login.headers["location"] == "/ui/candidates"

    candidates = client.get("/ui/candidates")
    assert candidates.status_code == 200
    assert "Demo Admin" in candidates.text

    csrf_token = _extract_csrf_token(candidates.text)
    logout = client.post("/logout", data={"csrf_token": csrf_token}, follow_redirects=False)
    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"

    after_logout = client.get("/ui/candidates", follow_redirects=False)
    assert after_logout.status_code == 303


def test_csrf_protects_authenticated_ui_form_actions(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "approver-1",
            "display_name": "Approver One",
            "password": "password-1",
            "roles": ["approver"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()
    login = _login(client, username="approver-1", password="password-1", next_path="/ui/entity/entity-1")
    assert login.status_code == 303

    response = client.post(
        "/ui/entity/entity-1/approve",
        data={"reason": "Approved after review."},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid_csrf_token"


def test_approval_action_records_authenticated_actor_from_session(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "approver-1",
            "display_name": "Approver One",
            "password": "password-1",
            "roles": ["approver"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()

    login = _login(client, username="approver-1", password="password-1", next_path="/ui/entity/entity-1")
    assert login.status_code == 303

    detail = client.get("/ui/entity/entity-1")
    csrf_token = _extract_csrf_token(detail.text)

    response = client.post(
        "/ui/entity/entity-1/approve",
        data={"reason": "Approved after operator review.", "csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303

    approved_events = [event for event in ledger.read() if event.get("event_type") == EventType.OUTBOUND_APPROVED.value]
    assert len(approved_events) == 1
    assert approved_events[0]["payload"]["actor"] == "approver-1"
    assert approved_events[0]["payload"]["actor_roles"] == ["approver"]


def test_send_action_records_authenticated_actor_from_session(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "sender-1",
            "display_name": "Sender One",
            "password": "password-1",
            "roles": ["sender"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()
    _seed_outbox_ready()

    login = _login(client, username="sender-1", password="password-1", next_path="/ui/entity/entity-1")
    assert login.status_code == 303

    detail = client.get("/ui/entity/entity-1")
    csrf_token = _extract_csrf_token(detail.text)

    response = client.post(
        "/ui/entity/entity-1/send-now",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303

    requested_events = [
        event for event in ledger.read() if event.get("event_type") == EventType.OUTBOUND_PROVIDER_SEND_REQUESTED.value
    ]
    sent_events = [event for event in ledger.read() if event.get("event_type") == EventType.OUTBOUND_SENT.value]
    assert len(requested_events) == 1
    assert requested_events[0]["payload"]["actor"] == "sender-1"
    assert requested_events[0]["payload"]["actor_roles"] == ["sender"]
    assert len(sent_events) == 1
    assert sent_events[0]["payload"]["actor"] == "sender-1"
    assert sent_events[0]["payload"]["actor_roles"] == ["sender"]


def test_basic_role_gating_blocks_reviewer_from_admin_and_approver_actions(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "reviewer-1",
            "display_name": "Reviewer One",
            "password": "password-1",
            "roles": ["reviewer"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()

    login = _login(client, username="reviewer-1", password="password-1")
    assert login.status_code == 303

    metrics = client.get("/ui/metrics", follow_redirects=False)
    detail = client.get("/ui/entity/entity-1")
    csrf_token = _extract_csrf_token(detail.text)
    approve = client.post(
        "/ui/entity/entity-1/approve",
        data={"reason": "Trying to approve.", "csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert metrics.status_code == 403
    assert approve.status_code == 403


def test_reviewer_cannot_send_or_manage_data_controls_by_direct_post(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "reviewer-1",
            "display_name": "Reviewer One",
            "password": "password-1",
            "roles": ["reviewer"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()
    _seed_outbox_ready()

    login = _login(client, username="reviewer-1", password="password-1", next_path="/ui/entity/entity-1")
    assert login.status_code == 303

    detail = client.get("/ui/entity/entity-1")
    csrf_token = _extract_csrf_token(detail.text)

    send = client.post(
        "/ui/entity/entity-1/send-now",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    suppression = client.post(
        "/data-controls/suppression",
        json={
            "target_type": "entity",
            "target_value": "entity-1",
            "reason": "manual_suppression",
            "entity_id": "entity-1",
            "actor": "reviewer-1",
        },
    )

    assert send.status_code == 403
    assert send.json()["detail"] == "insufficient_role"
    assert suppression.status_code == 403
    assert suppression.json()["detail"] == "insufficient_role"


def test_admin_session_can_access_data_controls_without_api_key(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "admin-1",
            "display_name": "Admin One",
            "password": "password-1",
            "roles": ["admin"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()

    login = _login(client, username="admin-1", password="password-1", next_path="/ui/entity/entity-1")
    assert login.status_code == 303

    suppression = client.post(
        "/data-controls/suppression",
        json={
            "target_type": "entity",
            "target_value": "entity-1",
            "reason": "manual_suppression",
            "entity_id": "entity-1",
            "source": "internal_admin",
            "notes": "Admin session suppression",
        },
    )

    assert suppression.status_code == 200
    assert suppression.json()["status"] == "recorded"


def test_metrics_require_admin_access_outside_dev(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "admin-1",
            "display_name": "Admin One",
            "password": "password-1",
            "roles": ["admin"],
        }
    )
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "HMAC_SECRET", "prod-hmac-secret-123456")
    monkeypatch.setattr(settings, "SESSION_SECRET", "prod-session-secret-123456")
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "OPERATOR_USERS_JSON", operator_users)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "prod-admin-key")
    client = TestClient(create_app())

    unauthenticated = client.get("/metrics", follow_redirects=False)
    with_api_key = client.get("/metrics", headers={"x-admin-api-key": "prod-admin-key"})
    login = _login(client, username="admin-1", password="password-1")
    assert login.status_code == 303
    with_session = client.get("/metrics")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"] == "authentication_required"
    assert with_api_key.status_code == 200
    assert with_session.status_code == 200


def test_ui_hides_protected_controls_for_reviewer_role(tmp_path, monkeypatch):
    operator_users = _operator_users_json(
        {
            "username": "reviewer-1",
            "display_name": "Reviewer One",
            "password": "password-1",
            "roles": ["reviewer"],
        }
    )
    client = _client(tmp_path, monkeypatch, operator_users_json=operator_users)
    _seed_candidate()
    _seed_draft()

    login = _login(client, username="reviewer-1", password="password-1")
    assert login.status_code == 303

    candidates = client.get("/ui/candidates")
    detail = client.get("/ui/entity/entity-1")

    assert candidates.status_code == 200
    assert 'href="/ui/metrics"' not in candidates.text
    assert detail.status_code == 200
    assert "Approve Draft" not in detail.text
    assert "Reject Draft" not in detail.text
    assert "Send Now" not in detail.text
    assert "cannot approve or reject drafts" in detail.text
