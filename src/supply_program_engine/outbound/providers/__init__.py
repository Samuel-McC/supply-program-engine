from __future__ import annotations

from supply_program_engine.config import settings
from supply_program_engine.outbound.providers.base import OutboundProvider
from supply_program_engine.outbound.providers.mock_provider import MockProvider


def get_provider() -> OutboundProvider:
    provider_name = settings.OUTBOUND_PROVIDER.strip().lower()
    if provider_name == "mock":
        return MockProvider()
    raise ValueError(f"Unsupported outbound provider: {settings.OUTBOUND_PROVIDER}")
