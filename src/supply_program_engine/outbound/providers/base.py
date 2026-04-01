from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSendRequest:
    draft_id: str
    entity_id: str
    to_hint: str | None
    subject: str
    body: str
    from_email: str
    from_name: str
    reply_to_email: str | None


@dataclass(frozen=True)
class ProviderSendResult:
    provider_name: str
    accepted: bool
    provider_message_id: str | None
    status: str
    failure_reason: str | None = None


class OutboundProvider:
    name: str = "base"

    def send(self, request: ProviderSendRequest) -> ProviderSendResult:
        raise NotImplementedError
