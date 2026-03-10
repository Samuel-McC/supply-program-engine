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


settings = Settings()