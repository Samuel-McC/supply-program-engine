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
    OUTBOUND_PROVIDER_SEND_REQUESTED = "outbound_provider_send_requested"
    OUTBOUND_PROVIDER_SEND_ACCEPTED = "outbound_provider_send_accepted"
    OUTBOUND_PROVIDER_SEND_FAILED = "outbound_provider_send_failed"
    OUTBOUND_SENT = "outbound_sent"
    REPLY_RECEIVED = "reply_received"
    REPLY_CLASSIFIED = "reply_classified"
    LEAD_INTERESTED = "lead_interested"
    LEAD_REJECTED = "lead_rejected"
    UNSUBSCRIBE_RECORDED = "unsubscribe_recorded"
    REPLY_TRIAGE_FAILED = "reply_triage_failed"
    OUTCOME_RECORDED = "outcome_recorded"
    SCORING_FEEDBACK_GENERATED = "scoring_feedback_generated"
    SOURCE_PERFORMANCE_UPDATED = "source_performance_updated"
    TEMPLATE_PERFORMANCE_UPDATED = "template_performance_updated"
    SUPPRESSION_RECORDED = "suppression_recorded"
    SUBJECT_REQUEST_RECORDED = "subject_request_recorded"
    SUBJECT_REQUEST_STATUS_UPDATED = "subject_request_status_updated"
    DATA_REDACTION_APPLIED = "data_redaction_applied"
    RETENTION_REVIEWED = "retention_reviewed"
    DATA_EXPORT_GENERATED = "data_export_generated"


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
    actor_roles: list[str] = Field(default_factory=list)
    reason: str


class InboundReply(BaseModel):
    entity_id: Optional[str] = None
    draft_id: Optional[str] = None
    provider_message_id: Optional[str] = None
    reply_text: str = Field(min_length=1)
    received_at: Optional[str] = None
    metadata: dict[str, object] = Field(default_factory=dict)


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
    draft_to_hint: Optional[str] = None
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
    provider_name: Optional[str] = None
    provider_message_id: Optional[str] = None
    provider_status: Optional[str] = None
    provider_requested_at: Optional[str] = None
    provider_accepted_at: Optional[str] = None
    provider_failed_at: Optional[str] = None
    provider_failure_reason: Optional[str] = None
    sent_at: Optional[str] = None

    reply_triage_status: Optional[str] = None
    last_reply_key: Optional[str] = None
    last_reply_classification: Optional[str] = None
    last_reply_received_at: Optional[str] = None
    last_reply_text_snippet: Optional[str] = None
    lead_interested: bool = False
    lead_rejected: bool = False
    unsubscribe_recorded: bool = False
    marketing_suppressed: bool = False
    marketing_suppression_reason: Optional[str] = None
    reply_out_of_office: bool = False
    reply_triage_error_type: Optional[str] = None
    reply_triage_error_message: Optional[str] = None
    reply_text_redacted: bool = False
    reply_text_redacted_at: Optional[str] = None
    latest_outcome: Optional[str] = None
    learning_outcome_version: Optional[str] = None
    learning_source_quality: Optional[str] = None
    learning_template_effectiveness: Optional[str] = None
    learning_reply_signal_strength: Optional[str] = None
    learning_source_performance_note: Optional[str] = None
    learning_template_performance_note: Optional[str] = None
    learning_last_updated_at: Optional[str] = None
    active_suppressions: list[dict[str, object]] = Field(default_factory=list)
    latest_subject_request_id: Optional[str] = None
    latest_subject_request_type: Optional[str] = None
    latest_subject_request_status: Optional[str] = None
    latest_subject_request_updated_at: Optional[str] = None
    subject_request_summaries: list[dict[str, object]] = Field(default_factory=list)
    retention_status: Optional[str] = None
    retention_last_reviewed_at: Optional[str] = None
    retention_notes: list[str] = Field(default_factory=list)

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
