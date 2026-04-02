from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.config import settings
from supply_program_engine.models import EventType
from supply_program_engine.queue import get_queue, reset_queue_backend
from supply_program_engine.queue.base import TaskMessage
from supply_program_engine.workers.runner import dispatch_task, run_once as worker_run_once


def _client_with_temp_ledger(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "QUEUE_BACKEND", "memory")
    reset_queue_backend()
    return TestClient(create_app())


def _append_candidate(entity_id: str, source: str = "manual") -> None:
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
                "source": source,
                "discovered_via": "industrial distributor",
            },
        }
    )


def _append_draft(entity_id: str, template_version: str = "v1") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-draft",
            "event_type": EventType.OUTBOUND_DRAFT_CREATED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": f"{entity_id}-draft",
                "entity_id": entity_id,
                "segment": "industrial_distributor",
                "subject": "Supply program",
                "body": "Hello",
                "template_version": template_version,
                "generation_mode": "deterministic",
            },
        }
    )


def _append_sent(entity_id: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-sent",
            "event_type": EventType.OUTBOUND_SENT.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "draft_id": f"{entity_id}-draft",
                "channel": "email",
                "status": "sent",
            },
        }
    )


def _append_interested(entity_id: str) -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-reply-classified",
            "event_type": EventType.REPLY_CLASSIFIED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "received_at": "2026-04-02T10:00:00+00:00",
                "reply_text_snippet": "Interested",
                "classification": "interested",
                "matched_phrase": "interested",
            },
        }
    )
    ledger.append(
        {
            "event_id": f"{entity_id}-lead-interested",
            "event_type": EventType.LEAD_INTERESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "reply_key": f"{entity_id}-reply",
                "classification": "interested",
            },
        }
    )


def test_queue_enqueue_and_worker_consume(tmp_path, monkeypatch):
    client = _client_with_temp_ledger(tmp_path, monkeypatch)

    enqueue_response = client.post(
        "/queue/enqueue",
        json={"task_type": "enrichment_run", "metadata": {"limit": 5}},
    )
    assert enqueue_response.status_code == 200
    assert enqueue_response.json()["status"] == "enqueued"

    worker_response = client.post("/worker/run-once")
    assert worker_response.status_code == 200
    body = worker_response.json()
    assert body["status"] == "processed"
    assert body["task_type"] == "enrichment_run"


def test_worker_dispatches_to_correct_runner(monkeypatch):
    called: list[tuple[str, int]] = []

    def fake_enrichment(limit: int = 50) -> dict:
        called.append(("enrichment", limit))
        return {"processed": 1}

    monkeypatch.setattr("supply_program_engine.workers.runner.enrichment_run_once", fake_enrichment)

    result = dispatch_task(
        TaskMessage(task_type="enrichment_run", correlation_id="c-dispatch", metadata={"limit": 7})
    )
    assert result["task_type"] == "enrichment_run"
    assert result["runner_result"] == {"processed": 1}
    assert called == [("enrichment", 7)]


def test_worker_execution_preserves_runner_idempotency(tmp_path, monkeypatch):
    _client_with_temp_ledger(tmp_path, monkeypatch)

    _append_candidate("entity-1")
    _append_draft("entity-1")
    _append_sent("entity-1")
    _append_interested("entity-1")

    queue = get_queue()
    queue.enqueue(TaskMessage(task_type="learning_run", correlation_id="c-learning-1"))
    queue.enqueue(TaskMessage(task_type="learning_run", correlation_id="c-learning-2"))

    first = worker_run_once(timeout_seconds=0)
    second = worker_run_once(timeout_seconds=0)

    assert first["status"] == "processed"
    assert second["status"] == "processed"

    outcomes = [e for e in ledger.read() if e.get("event_type") == EventType.OUTCOME_RECORDED.value]
    assert len(outcomes) == 1


def test_queue_endpoint_returns_503_when_redis_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "QUEUE_BACKEND", "redis")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    reset_queue_backend()
    client = TestClient(create_app())

    response = client.post("/queue/enqueue", json={"task_type": "sender_run"})

    assert response.status_code == 503
    assert response.json()["detail"].startswith("queue_unavailable:")
