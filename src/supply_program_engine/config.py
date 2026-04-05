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
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", os.getenv("HMAC_SECRET", "dev-secret"))
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "spe_operator_session")
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
    SESSION_COOKIE_HTTPONLY: bool = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SECURE: bool = os.getenv(
        "SESSION_COOKIE_SECURE",
        "false" if os.getenv("ENV", "dev") == "dev" else "true",
    ).lower() == "true"
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
    OPERATOR_USERS_JSON: str = os.getenv("OPERATOR_USERS_JSON", "")

    HOST: str = os.getenv("HOST", "0.0.0.0")
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
    OUTBOUND_PROVIDER: str = os.getenv("OUTBOUND_PROVIDER", "mock")
    OUTBOUND_DRY_RUN: bool = os.getenv("OUTBOUND_DRY_RUN", "true").lower() == "true"
    OUTBOUND_FROM_EMAIL: str = os.getenv("OUTBOUND_FROM_EMAIL", "operator@example.internal")
    OUTBOUND_FROM_NAME: str = os.getenv("OUTBOUND_FROM_NAME", "Supply Program")
    OUTBOUND_REPLY_TO_EMAIL: str | None = os.getenv("OUTBOUND_REPLY_TO_EMAIL")
    OUTBOUND_PROVIDER_API_KEY: str | None = os.getenv("OUTBOUND_PROVIDER_API_KEY")
    SEND_POLICY_RISK_THRESHOLD: int = int(os.getenv("SEND_POLICY_RISK_THRESHOLD", "3"))
    SUPPRESSED_ENTITIES: str = os.getenv("SUPPRESSED_ENTITIES", "")
    SUPPRESSED_DOMAINS: str = os.getenv("SUPPRESSED_DOMAINS", "")
    QUEUE_BACKEND: str = os.getenv("QUEUE_BACKEND", "memory")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    QUEUE_NAME: str = os.getenv("QUEUE_NAME", "spe:tasks")
    WORKER_ENABLED: bool = os.getenv("WORKER_ENABLED", "false").lower() == "true"
    WORKER_POLL_TIMEOUT_SECONDS: int = int(os.getenv("WORKER_POLL_TIMEOUT_SECONDS", "5"))
    OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "supply-program-engine")
    OTEL_EXPORTER_TYPE: str = os.getenv("OTEL_EXPORTER_TYPE", "console")
    REPLY_TEXT_RETENTION_DAYS: int = int(os.getenv("REPLY_TEXT_RETENTION_DAYS", "30"))
    REDACTION_PLACEHOLDER: str = os.getenv("REDACTION_PLACEHOLDER", "[redacted]")



settings = Settings()
