from __future__ import annotations

from urllib.parse import urlparse

from supply_program_engine.enrichment.fetch import FetchedWebsite

SIGNAL_VERSION = "enrichment_v1"

CONSTRUCTION_KEYWORDS = (
    "construction",
    "contractor",
    "formwork",
    "builder",
    "concrete",
    "building supply",
)
DISTIBUTOR_KEYWORDS = (
    "distributor",
    "wholesale",
    "supplier",
    "industrial supply",
    "building materials",
)
B2B_KEYWORDS = (
    "procurement",
    "commercial",
    "trade",
    "projects",
    "industrial",
    "contractor",
    "distributor",
)


def _normalize_text(*parts: str | None) -> str:
    return " ".join(part.strip().lower() for part in parts if part and part.strip())


def _match_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return sorted({keyword for keyword in keywords if keyword in text})


def _extract_domain(website: str | None) -> str | None:
    if not website:
        return None

    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = parsed.netloc or parsed.path
    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def derive_signals(
    *,
    company_name: str,
    discovered_via: str | None,
    source: str | None,
    website: str | None,
    fetched: FetchedWebsite | None = None,
) -> dict:
    text = _normalize_text(
        company_name,
        discovered_via,
        source,
        fetched.title if fetched else None,
        fetched.meta_description if fetched else None,
        fetched.html if fetched else None,
    )

    construction_matches = _match_keywords(text, CONSTRUCTION_KEYWORDS)
    distributor_matches = _match_keywords(text, DISTIBUTOR_KEYWORDS)
    b2b_matches = _match_keywords(text, B2B_KEYWORDS)

    contact_page_detected = False
    if fetched:
        contact_page_detected = (
            'href="/contact' in fetched.html.lower()
            or "contact us" in fetched.html.lower()
            or "get in touch" in fetched.html.lower()
        )

    matched_keywords = sorted(set(construction_matches + distributor_matches + b2b_matches))

    return {
        "signal_version": SIGNAL_VERSION,
        "source": "website_fetch" if fetched else "heuristic_only",
        "domain": _extract_domain(website),
        "website_present": bool(website),
        "fetch_succeeded": fetched is not None,
        "website_title": fetched.title if fetched else None,
        "meta_description": fetched.meta_description if fetched else None,
        "contact_page_detected": contact_page_detected,
        "construction_keywords_found": bool(construction_matches),
        "distributor_keywords_found": bool(distributor_matches),
        "likely_b2b": bool(distributor_matches or b2b_matches),
        "matched_keywords": matched_keywords,
    }
