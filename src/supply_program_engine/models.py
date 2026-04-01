from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    CANDIDATE_INGESTED = "candidate_ingested"
    ENRICHMENT_STARTED = "enrichment_started"
    ENRICHMENT_COMPLETED = "enrichment_completed"
    ENRICHMENT_FAILED = "enrichment_failed"
    QUALIFICATION_COMPUTED = "qualification_computed"
    OUTBOUND_DRAFT_CREATED = "outbound_draft_created"
    OUTBOUND_APPROVED = "outbound_approved"
    OUTBOUND_REJECTED = "outbound_rejected"
    OUTBOX_READY = "outbox_ready"
    OUTBOUND_SEND_BLOCKED = "outbound_send_blocked"
    OUTBOUND_SENT = "outbound_sent"


class Candidate(BaseModel):
    company_name: str
    website: Optional[str] = None
    location: str
    source: str
    discovered_via: str

    external_id: Optional[str] = None
    source_query: Optional[str] = None
    source_region: Optional[str] = None
    source_confidence: Optional[float] = None



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

    evidence: list[str] = Field(default_factory=list)
    scoring_version: str = "v1"

    risk_score: int = 0
    requires_manual_review: bool = False
    policy_version: str = "v1"
    compliance_findings: list[str] = Field(default_factory=list)


class OutboundDraft(BaseModel):
    draft_id: str
    entity_id: str
    segment: str
    channel: Literal["email"] = "email"
    subject: str
    body: str
    to_hint: Optional[str] = None
    status: Literal["draft"] = "draft"

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
    "outbox_ready",
    "send_blocked",
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

    scoring_version: str = "v1"
    requires_manual_review: bool = False
    risk_score: int = 0
    policy_version: str = "v1"
    compliance_findings: list[str] = Field(default_factory=list)

    outbox_ready: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    blocked_at: Optional[str] = None
    sent_at: Optional[str] = None

    enrichment_status: Optional[str] = None
    enrichment_source: Optional[str] = None
    enrichment_version: Optional[str] = None
    enrichment_domain: Optional[str] = None
    enrichment_website_present: bool = False
    enrichment_fetch_succeeded: bool = False
    enrichment_contact_page_detected: bool = False
    enrichment_construction_keywords_found: bool = False
    enrichment_distributor_keywords_found: bool = False
    enrichment_likely_b2b: bool = False
    enrichment_matched_keywords: list[str] = Field(default_factory=list)
    enrichment_website_title: Optional[str] = None
    enrichment_meta_description: Optional[str] = None
    enrichment_error_type: Optional[str] = None
    enrichment_error_message: Optional[str] = None

    source: Optional[str] = None
    discovered_via: Optional[str] = None
    external_id: Optional[str] = None
    source_query: Optional[str] = None
    source_region: Optional[str] = None
    source_confidence: Optional[float] = None
