from __future__ import annotations

from typing import List

import requests

from supply_program_engine.config import settings
from ..models import DiscoveredCompany


def discover_text_search(
    text_query: str,
    region_hint: str | None = None,
    max_results: int = 10,
) -> List[DiscoveredCompany]:
    if not settings.GOOGLE_PLACES_API_KEY:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not configured")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.websiteUri"
        ),
    }

    body = {
        "textQuery": text_query,
        "pageSize": max_results,
    }

    if region_hint:
        # Keep this simple for now: just include region in the query string for discovery relevance.
        body["textQuery"] = f"{text_query} in {region_hint}"

    response = requests.post(
        settings.GOOGLE_PLACES_TEXT_SEARCH_URL,
        headers=headers,
        json=body,
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    places = data.get("places", [])

    discovered: list[DiscoveredCompany] = []

    for place in places:
        display_name = (place.get("displayName") or {}).get("text")
        if not display_name:
            continue

        discovered.append(
            DiscoveredCompany(
                company_name=display_name,
                website=place.get("websiteUri"),
                location=place.get("formattedAddress"),
                source="google_places_api",
                discovered_via=text_query,
                external_id=place.get("id"),
                source_query=text_query,
                source_region=region_hint,
                source_confidence=0.8,
            )
        )

    return discovered
