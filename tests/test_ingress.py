import hmac
import hashlib

from fastapi.testclient import TestClient

from supply_program_engine.api import create_app
from supply_program_engine.config import settings


def _sign(body: bytes) -> str:
    return hmac.new(settings.HMAC_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_ingest_idempotent_dev(monkeypatch, tmp_path):
    # Use temp ledger
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "ENV", "dev")  # signature not required in dev

    app = create_app()
    client = TestClient(app)

    payload = {
        "company_name": "Acme Formwork",
        "website": "https://acmeformwork.com",
        "location": "TX",
        "source": "manual",
        "discovered_via": "formwork contractor",
    }

    r1 = client.post("/ingress/candidate", json=payload)
    assert r1.status_code == 200
    assert r1.json()["status"] == "ingested"

    r2 = client.post("/ingress/candidate", json=payload)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


def test_ingest_requires_signature_outside_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "ENV", "prod")  # signature required
    monkeypatch.setattr(settings, "HMAC_SECRET", "prod-hmac-secret-123456")
    monkeypatch.setattr(settings, "SESSION_SECRET", "prod-session-secret-123456")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "prod-admin-key")

    app = create_app()
    client = TestClient(app)

    payload = {
        "company_name": "Globex Lumber",
        "website": "https://globexlumber.com",
        "location": "CA",
        "source": "manual",
        "discovered_via": "industrial lumber distributor",
    }

    # Missing signature -> 401
    r1 = client.post("/ingress/candidate", json=payload)
    assert r1.status_code == 401

    # With correct signature -> 200
    body = client.build_request("POST", "/ingress/candidate", json=payload).content
    sig = _sign(body)

    r2 = client.post("/ingress/candidate", content=body, headers={"X-Signature": sig, "Content-Type": "application/json"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "ingested"
