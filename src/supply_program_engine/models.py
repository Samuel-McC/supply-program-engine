from enum import Enum
from pydantic import BaseModel
from typing import Optional


class Segment(str, Enum):
    INDUSTRIAL_DISTRIBUTOR = "industrial_distributor"
    REGIONAL_SUPPLIER = "regional_supplier"
    MODULAR_MANUFACTURER = "modular_manufacturer"
    CONCRETE_CONTRACTOR = "concrete_contractor"
    SCAFFOLD_RENTAL = "scaffold_rental"


class State(str, Enum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    DRAFTED = "drafted"
    PACKET_BUILT = "packet_built"
    COMPLIANCE_PASSED = "compliance_passed"
    PROPOSED = "proposed"
    APPROVED = "approved"
    SENT = "sent"


class Candidate(BaseModel):
    company_name: str
    website: Optional[str]
    location: str
    source: str
    discovered_via: str