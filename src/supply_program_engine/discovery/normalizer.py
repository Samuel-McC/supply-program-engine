from __future__ import annotations

from .models import DiscoveredCompany


def normalize_company(company: DiscoveredCompany) -> dict:
    return {
        "company_name": company.company_name.strip(),
        "website": company.website,
        "location": company.location,
        "source": company.source,
        "discovered_via": company.discovered_via,
        "external_id": company.external_id,
        "source_query": company.source_query,
        "source_region": company.source_region,
        "source_confidence": company.source_confidence,
    }
