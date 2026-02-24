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


from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    CANDIDATE_INGESTED = "candidate_ingested"
    QUALIFICATION_COMPUTED = "qualification_computed"
    OUTREACH_DRAFTED = "outreach_drafted"
    PACKET_BUILT = "packet_built"
    COMPLIANCE_CHECKED = "compliance_checked"
    PROPOSAL_CREATED = "proposal_created"
    HUMAN_DECISION = "human_decision"
    OUTBOX_CREATED = "outbox_created"
    OUTBOX_SENT = "outbox_sent"
    ERROR_RECORDED = "error_recorded"
    OUTBOUND_DRAFT_CREATED = "outbound_draft_created"
    OUTBOUND_APPROVED = "outbound_approved"
    OUTBOUND_REJECTED = "outbound_rejected"
    OUTBOUND_SENT = "outbound_sent"


class LedgerEvent(BaseModel):
    event_id: str
    event_type: EventType
    correlation_id: str
    entity_id: str  # e.g., stable id for a company/candidate
    ts: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any]
    prev_hash: Optional[str] = None
    hash: Optional[str] = None

from typing import Literal, Optional

Segment = Literal[
    "industrial_distributor",
    "regional_building_supplier",
    "concrete_contractor_large",
    "modular_manufacturer",
    "unknown",
]


class Qualification(BaseModel):
    segment: Segment
    priority_score: int  # 0–10
    estimated_containers_per_month: int  # conservative integer
    decision_maker_type: str  # e.g. "Procurement", "Owner", "Ops Manager"
    notes: Optional[str] = None

from pydantic import BaseModel
from typing import Optional, Literal

class OutboundDraft(BaseModel):
    draft_id: str
    entity_id: str
    segment: str
    channel: Literal["email"] = "email"
    subject: str
    body: str
    to_hint: Optional[str] = None  # placeholder, real contact later
    status: Literal["draft"] = "draft"

class ApprovalDecision(BaseModel):
    draft_id: str
    decision: Literal["approved", "rejected"]
    actor: str  # who approved/rejected (user/email/service principal)
    reason: Optional[str] = None

from typing import Optional, Literal

PipelineStatus = Literal[
    "candidate_ingested",
    "qualified",
    "draft_created",
    "approved",
    "rejected",
    "sent",
]

class PipelineEntityView(BaseModel):
    entity_id: str
    company_name: str
    website: Optional[str] = None
    location: Optional[str] = None

    segment: str = "unknown"
    priority_score: int = 0
    estimated_containers_per_month: int = 0
    decision_maker_type: str = "Unknown"

    status: PipelineStatus = "candidate_ingested"
    last_event_ts: Optional[str] = None  # keep string for now (ISO)
    correlation_id: Optional[str] = None

    draft_id: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None