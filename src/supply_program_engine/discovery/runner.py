from __future__ import annotations

import requests

from .normalizer import normalize_company
from .sources.mock_source import discover

BASE_URL = "http://127.0.0.1:8000"
INGRESS_ENDPOINT = f"{BASE_URL}/ingress/candidate"
ORCHESTRATOR_ENDPOINT = f"{BASE_URL}/orchestrator/run-once?limit=50"
OUTBOUND_ENDPOINT = f"{BASE_URL}/outbound/run-once?limit=50"


def run_discovery() -> dict:
    discovered = discover()

    ingest_results: list[dict] = []

    for company in discovered:
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
        "ingest_results": ingest_results,
        "orchestrator": {
            "status_code": orchestrator_response.status_code,
            "response": orchestrator_body,
        },
        "outbound": {
            "status_code": outbound_response.status_code,
            "response": outbound_body,
        },
    }


if __name__ == "__main__":
    output = run_discovery()
    print(output)
