from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field


SuppressionTargetType = Literal["entity", "domain", "email"]
SuppressionReason = Literal[
    "unsubscribe",
    "manual_suppression",
    "objection_to_marketing",
    "compliance_hold",
]
SubjectRequestType = Literal["erasure", "access_export", "rectification", "objection_to_marketing"]
SubjectRequestStatus = Literal["requested", "in_review", "approved", "completed", "rejected"]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def normalize_target_value(target_type: SuppressionTargetType, value: str) -> str:
    normalized = value.strip()
    if target_type == "entity":
        return normalized
    if target_type == "email":
        return normalized.lower()

    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


class SuppressionRecord(BaseModel):
    target_type: SuppressionTargetType
    target_value: str
    reason: SuppressionReason
    created_at: str | None = None
    expires_at: str | None = None
    actor: str | None = None
    source: str = "internal_admin"
    notes: str | None = None
    entity_id: str | None = None


class SubjectRequestRecord(BaseModel):
    request_id: str | None = None
    request_type: SubjectRequestType
    target_type: SuppressionTargetType
    target_value: str
    status: SubjectRequestStatus = "requested"
    requested_at: str | None = None
    entity_id: str | None = None
    actor: str | None = None
    source: str = "internal_admin"
    notes: str | None = None


class SubjectRequestStatusUpdate(BaseModel):
    request_id: str
    status: SubjectRequestStatus
    updated_at: str | None = None
    actor: str | None = None
    notes: str | None = None


class RedactionState(BaseModel):
    reply_key: str
    entity_id: str | None = None
    target_event_id: str
    fields_redacted: list[str] = Field(default_factory=list)
    replacement_text: str
    reason: str
    source: str
    applied_at: str
    actor: str | None = None
    subject_request_id: str | None = None
