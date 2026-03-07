from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    CANDIDATE_INGESTED = "candidate_ingested"
    QUALIFICATION_COMPUTED = "qualification_computed"
    OUTBOUND_DRAFT_CREATED = "outbound_draft_created"
    OUTBOUND_APPROVED = "outbound_approved"
    OUTBOUND_REJECTED = "outbound_rejected"
    OUTBOUND_SENT = "outbound_sent"


class Candidate(BaseModel):
    company_name: str
    website: Optional[str] = None
    location: str
    source: str
    discovered_via: str


Segment = Literal[
    "industrial_distributor",
    "regional_building_supplier",
    "concrete_contractor_large",
    "modular_manufacturer",
    "unknown",
]


class Qualification(BaseModel):
    segment: Segment
    priority_score: int = Field(ge=0, le=10)
    estimated_containers_per_month: int = Field(ge=0)
    decision_maker_type: str
    notes: Optional[str] = None

    # Phase 3 hardening
    evidence: list[str] = Field(default_factory=list)
    scoring_version: str = "v1"


class OutboundDraft(BaseModel):
    draft_id: str
    entity_id: str
    segment: str
    channel: Literal["email"] = "email"
    subject: str
    body: str
    to_hint: Optional[str] = None
    status: Literal["draft"] = "draft"

    # Phase 4 hardening
    template_version: str = "v1"
    generation_mode: Literal["deterministic", "llm_assisted"] = "deterministic"


class ApprovalDecision(BaseModel):
    draft_id: str
    decision: Literal["approved", "rejected"]
    actor: str
    reason: str


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
    last_event_ts: Optional[str] = None
    correlation_id: Optional[str] = None

    draft_id: Optional[str] = None
    draft_subject: Optional[str] = None
    draft_body: Optional[str] = None
    template_version: Optional[str] = None

    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    last_decision_reason: Optional[str] = None

    # Phase 5 hardening
    scoring_version: str = "v1"
    requires_manual_review: bool = False
    risk_score: int = 0