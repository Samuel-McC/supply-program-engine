from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class DiscoveredCompany(BaseModel):
    company_name: str
    website: Optional[str] = None
    location: Optional[str] = None
    source: str
    discovered_via: str

    external_id: Optional[str] = None
    source_query: Optional[str] = None
    source_region: Optional[str] = None
    source_confidence: Optional[float] = None
