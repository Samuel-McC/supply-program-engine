import requests

from supply_program_engine import ledger
from supply_program_engine.config import settings
from supply_program_engine.enrichment.runner import run_once
from supply_program_engine.models import EventType


def _append_candidate(entity_id: str, website: str | None = "https://acme.example") -> None:
    ledger.append(
        {
            "event_id": f"{entity_id}-candidate",
            "event_type": EventType.CANDIDATE_INGESTED.value,
            "correlation_id": "c1",
            "entity_id": entity_id,
            "payload": {
                "company_name": "Acme Distributor",
                "website": website,
                "location": "TX",
                "source": "manual",
                "discovered_via": "industrial distributor",
            },
        }
    )


def test_enrichment_runner_emits_started_and_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    class FakeResponse:
        status_code = 200
        url = "https://acme.example"
        text = """
        <html>
            <head>
                <title>Acme Industrial Distributor</title>
                <meta name="description" content="Commercial distributor and contractor supply partner">
            </head>
            <body><a href="/contact">Contact</a></body>
        </html>
        """

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "supply_program_engine.enrichment.fetch.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )

    _append_candidate("entity-1")

    result = run_once(limit=10)

    assert result["started"] == 1
    assert result["completed"] == 1
    assert result["failed"] == 0

    events = list(ledger.read())
    completed = [e for e in events if e.get("event_type") == EventType.ENRICHMENT_COMPLETED.value]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    assert payload["website_present"] is True
    assert payload["fetch_succeeded"] is True
    assert payload["contact_page_detected"] is True
    assert payload["distributor_keywords_found"] is True
    assert payload["likely_b2b"] is True
    assert payload["website_title"] == "Acme Industrial Distributor"

    rerun = run_once(limit=10)
    assert rerun["skipped_duplicates"] == 1


def test_enrichment_runner_emits_failed_event_on_fetch_error(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("supply_program_engine.enrichment.fetch.requests.get", raise_timeout)

    _append_candidate("entity-2", website="https://timeout.example")

    result = run_once(limit=10)

    assert result["started"] == 1
    assert result["completed"] == 0
    assert result["failed"] == 1

    events = list(ledger.read())
    failed = [e for e in events if e.get("event_type") == EventType.ENRICHMENT_FAILED.value]
    assert len(failed) == 1
    assert failed[0]["payload"]["website_present"] is True
    assert failed[0]["payload"]["error_type"] == "timeout"
