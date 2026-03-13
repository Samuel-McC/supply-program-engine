from __future__ import annotations

import os
import requests

from .normalizer import normalize_company
from .sources.mock_source import discover as discover_mock
from .sources.google_places import discover_text_search

BASE_URL = "http://127.0.0.1:8000"
INGRESS_ENDPOINT = f"{BASE_URL}/ingress/candidate"
ORCHESTRATOR_ENDPOINT = f"{BASE_URL}/orchestrator/run-once?limit=50"
OUTBOUND_ENDPOINT = f"{BASE_URL}/outbound/run-once?limit=50"


def _ingest_companies(companies: list) -> list[dict]:
    ingest_results: list[dict] = []

    for company in companies:
        payload = normalize_company(company)

        response = requests.post(
            INGRESS_ENDPOINT,
            json=payload,
            timeout=10,
        )

        try:
            response_body = response.json()
        except Exception:
            response_body = {"raw": response.text}

        ingest_results.append(
            {
                "company": payload["company_name"],
                "status_code": response.status_code,
                "response": response_body,
            }
        )

    return ingest_results


def _advance_pipeline() -> dict:
    orchestrator_response = requests.post(
        ORCHESTRATOR_ENDPOINT,
        timeout=10,
    )
    try:
        orchestrator_body = orchestrator_response.json()
    except Exception:
        orchestrator_body = {"raw": orchestrator_response.text}

    outbound_response = requests.post(
        OUTBOUND_ENDPOINT,
        timeout=10,
    )
    try:
        outbound_body = outbound_response.json()
    except Exception:
        outbound_body = {"raw": outbound_response.text}

    return {
        "orchestrator": {
            "status_code": orchestrator_response.status_code,
            "response": orchestrator_body,
        },
        "outbound": {
            "status_code": outbound_response.status_code,
            "response": outbound_body,
        },
    }


def run_mock_discovery() -> dict:
    companies = discover_mock()
    ingest_results = _ingest_companies(companies)
    pipeline_results = _advance_pipeline()

    return {
        "source": "mock",
        "ingest_results": ingest_results,
        **pipeline_results,
    }


def run_google_places_discovery(
    query: str,
    region: str,
    max_results: int = 10,
) -> dict:
    companies = discover_text_search(
        text_query=query,
        region_hint=region,
        max_results=max_results,
    )
    ingest_results = _ingest_companies(companies)
    pipeline_results = _advance_pipeline()

    return {
        "source": "google_places_api",
        "query": query,
        "region": region,
        "count": len(companies),
        "ingest_results": ingest_results,
        **pipeline_results,
    }


if __name__ == "__main__":
    mode = os.getenv("DISCOVERY_MODE", "mock")

    if mode == "google_places":
        query = os.getenv("DISCOVERY_QUERY", "formwork contractor")
        region = os.getenv("DISCOVERY_REGION", "Texas")
        output = run_google_places_discovery(query=query, region=region, max_results=10)
    else:
        output = run_mock_discovery()

    print(output)
