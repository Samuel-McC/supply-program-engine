from __future__ import annotations

import hashlib

from supply_program_engine.config import settings
from supply_program_engine.outbound.providers.base import (
    OutboundProvider,
    ProviderSendRequest,
    ProviderSendResult,
)


class MockProvider(OutboundProvider):
    name = "mock"

    def send(self, request: ProviderSendRequest) -> ProviderSendResult:
        message_id = hashlib.sha256(
            f"{request.entity_id}|{request.draft_id}|{request.subject}".encode("utf-8")
        ).hexdigest()[:24]

        if not settings.OUTBOUND_DRY_RUN and settings.OUTBOUND_PROVIDER_API_KEY == "fail":
            return ProviderSendResult(
                provider_name=self.name,
                accepted=False,
                provider_message_id=None,
                status="failed",
                failure_reason="provider_rejected_request",
            )

        return ProviderSendResult(
            provider_name=self.name,
            accepted=True,
            provider_message_id=f"mock-{message_id}",
            status="accepted" if settings.OUTBOUND_DRY_RUN else "sent",
        )
