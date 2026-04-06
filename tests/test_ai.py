from fastapi.testclient import TestClient

from supply_program_engine import ledger
from supply_program_engine.api import create_app
from supply_program_engine.ai.models import AIDraftContext
from supply_program_engine.ai.provider import OpenAIDraftProvider
from supply_program_engine.config import settings
from supply_program_engine.models import EventType


def _client(
    tmp_path,
    monkeypatch,
    *,
    ai_enabled: bool = True,
    ai_drafts_enabled: bool = True,
    ai_provider: str = "mock",
    ai_model: str = "gpt-5.4-mini",
    openai_api_key: str | None = None,
) -> TestClient:
    monkeypatch.setattr(settings, "LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")
    monkeypatch.setattr(settings, "ENV", "dev")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setattr(settings, "AI_ENABLED", ai_enabled)
    monkeypatch.setattr(settings, "AI_DRAFTS_ENABLED", ai_drafts_enabled)
    monkeypatch.setattr(settings, "AI_PROVIDER", ai_provider)
    monkeypatch.setattr(settings, "AI_MODEL", ai_model)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", openai_api_key)
    return TestClient(create_app())


def _admin_headers() -> dict[str, str]:
    return {"x-admin-api-key": "test-admin-key"}


def _append_candidate(entity_id: str = "entity-1") -> None:
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
                "source": "mock_directory",
                "discovered_via": "industrial distributor",
                "source_query": "industrial distributor texas",
                "source_region": "Texas",
            },
        }
    )


def _append_draft(entity_id: str = "entity-1", draft_id: str = "draft-1") -> None:
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
                "subject": "Film-faced eucalyptus panel supply program for Acme Panels",
                "body": (
                    "Hi Acme Panels,\n\n"
                    "We support industrial_distributor buyers in TX with a structural panel supply program.\n\n"
                    "If relevant, we can share specs and pricing.\n\n"
                    "Regards,\n"
                    "Supply Program"
                ),
                "template_version": "v2_merge_fields",
                "generation_mode": "deterministic",
            },
        }
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200, headers: dict[str, str] | None = None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload


def test_openai_provider_parses_structured_response(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "id": "resp_123",
                "status": "completed",
                "usage": {"input_tokens": 111, "output_tokens": 44, "total_tokens": 155},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"suggested_subject":"Acme Panels: tailored panel supply idea",'
                                    '"suggested_opening":"A tailored opening paragraph.",'
                                    '"suggested_body":"Hi Acme Panels,\\n\\nA tailored opening paragraph.\\n\\nRegards,\\nSupply Program"}'
                                ),
                            }
                        ],
                    }
                ],
            },
            headers={"x-request-id": "req_123"},
        )

    monkeypatch.setattr("supply_program_engine.ai.provider.requests.post", fake_post)

    provider = OpenAIDraftProvider(model_name="gpt-5.4-mini", api_key="test-openai-key")
    suggestion = provider.suggest_draft(
        context=AIDraftContext(
            entity_id="entity-1",
            company_name="Acme Panels",
            location="TX",
            segment="industrial_distributor",
            source="mock_directory",
            discovered_via="industrial distributor",
            source_query="industrial distributor texas",
            source_region="Texas",
            enrichment_summary=["distributor_keywords_found", "likely_b2b"],
            deterministic_draft_id="draft-1",
            deterministic_subject="Deterministic subject",
            deterministic_body="Deterministic body",
            deterministic_template_version="v2_merge_fields",
        ),
        prompt="Prompt text",
        prompt_version="ai_draft_personalizer_v1",
    )

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 15
    assert captured["headers"]["Authorization"] == "Bearer test-openai-key"
    payload = captured["json"]
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "ai_draft_suggestion"

    assert suggestion.provider_name == "openai"
    assert suggestion.model_name == "gpt-5.4-mini"
    assert suggestion.provider_response_id == "resp_123"
    assert suggestion.suggested_subject == "Acme Panels: tailored panel supply idea"
    assert suggestion.usage_metadata["input_tokens"] == 111
    assert suggestion.provider_metadata["request_id"] == "req_123"


def test_ai_draft_endpoint_emits_openai_suggestion_event(tmp_path, monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        return _FakeResponse(
            {
                "id": "resp_openai_1",
                "status": "completed",
                "usage": {"input_tokens": 99, "output_tokens": 33, "total_tokens": 132},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"suggested_subject":"Acme Panels: tailored panel supply idea",'
                                    '"suggested_opening":"A tailored opening paragraph.",'
                                    '"suggested_body":"Hi Acme Panels,\\n\\nA tailored opening paragraph.\\n\\nRegards,\\nSupply Program"}'
                                ),
                            }
                        ],
                    }
                ],
            },
            headers={"x-request-id": "req_openai_1"},
        )

    monkeypatch.setattr("supply_program_engine.ai.provider.requests.post", fake_post)
    client = _client(tmp_path, monkeypatch, ai_provider="openai", openai_api_key="test-openai-key")
    _append_candidate()
    _append_draft()

    response = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "suggested"
    assert body["entity_id"] == "entity-1"
    assert body["source_draft_id"] == "draft-1"
    assert body["provider_name"] == "openai"
    assert body["model_name"] == "gpt-5.4-mini"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_SUGGESTED.value]
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["source_draft_id"] == "draft-1"
    assert payload["provider_name"] == "openai"
    assert payload["model_name"] == "gpt-5.4-mini"
    assert payload["prompt_version"] == "ai_draft_personalizer_v1"
    assert payload["provider_response_id"] == "resp_openai_1"
    assert payload["usage_metadata"]["input_tokens"] == 99
    assert payload["generated_at"]
    assert payload["suggested_subject"]
    assert payload["suggested_opening"]
    assert payload["suggested_body"]


def test_ai_draft_endpoint_emits_failure_event_when_openai_api_key_is_missing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, ai_provider="openai", openai_api_key=None)
    _append_candidate()
    _append_draft()

    response = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "openai_api_key_missing"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_GENERATION_FAILED.value]
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["source_draft_id"] == "draft-1"
    assert payload["provider_name"] == "openai"
    assert payload["model_name"] == "gpt-5.4-mini"
    assert payload["prompt_version"] == "ai_draft_personalizer_v1"
    assert payload["failure_reason"] == "openai_api_key_missing"
    deterministic_drafts = [
        event for event in ledger.read() if event.get("event_type") == EventType.OUTBOUND_DRAFT_CREATED.value
    ]
    ai_suggestions = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_SUGGESTED.value]
    assert len(deterministic_drafts) == 1
    assert ai_suggestions == []


def test_ai_draft_endpoint_is_idempotent_for_same_source_draft(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _append_candidate()
    _append_draft()

    first = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())
    second = client.post("/ai/drafts/suggest/entity-1", headers=_admin_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "suggested"
    assert second.json()["status"] == "duplicate"

    events = [event for event in ledger.read() if event.get("event_type") == EventType.AI_DRAFT_SUGGESTED.value]
    assert len(events) == 1
