from __future__ import annotations

import os

from pydantic import BaseModel


class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "supply-program-engine")
    ENV: str = os.getenv("ENV", "dev")

    LEDGER_PATH: str = os.getenv("LEDGER_PATH", "data/ledger.jsonl")
    LEDGER_BACKEND: str = os.getenv("LEDGER_BACKEND", "file")
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

    HMAC_SECRET: str = os.getenv("HMAC_SECRET", "dev-secret")
    ADMIN_API_KEY: str | None = os.getenv("ADMIN_API_KEY")

    HOST: str = os.getenv("HOST", "0.0.0.0") # nosec B104
    PORT: int = int(os.getenv("PORT", "8000"))

    GOOGLE_PLACES_API_KEY: str | None = os.getenv("GOOGLE_PLACES_API_KEY")
    GOOGLE_PLACES_TEXT_SEARCH_URL: str = os.getenv(
        "GOOGLE_PLACES_TEXT_SEARCH_URL",
        "https://places.googleapis.com/v1/places:searchText",
    )
    ENRICHMENT_FETCH_TIMEOUT_SECONDS: int = int(os.getenv("ENRICHMENT_FETCH_TIMEOUT_SECONDS", "5"))
    ENRICHMENT_USER_AGENT: str = os.getenv(
        "ENRICHMENT_USER_AGENT",
        "supply-program-engine-enrichment/1.0",
    )
    SEND_POLICY_RISK_THRESHOLD: int = int(os.getenv("SEND_POLICY_RISK_THRESHOLD", "3"))
    SUPPRESSED_ENTITIES: str = os.getenv("SUPPRESSED_ENTITIES", "")
    SUPPRESSED_DOMAINS: str = os.getenv("SUPPRESSED_DOMAINS", "")



settings = Settings()
