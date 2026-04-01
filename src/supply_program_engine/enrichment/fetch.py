from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from supply_program_engine.config import settings


@dataclass(frozen=True)
class FetchedWebsite:
    final_url: str
    status_code: int
    html: str
    title: str | None
    meta_description: str | None


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return value[:160] if value else None


def _extract_meta_description(html: str) -> str | None:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        match = re.search(
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return value[:240] if value else None


def fetch_public_website(url: str) -> FetchedWebsite:
    response = requests.get(
        url,
        timeout=settings.ENRICHMENT_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": settings.ENRICHMENT_USER_AGENT},
    )
    response.raise_for_status()

    html = response.text[:50000]

    return FetchedWebsite(
        final_url=str(getattr(response, "url", url) or url),
        status_code=int(getattr(response, "status_code", 200) or 200),
        html=html,
        title=_extract_title(html),
        meta_description=_extract_meta_description(html),
    )
