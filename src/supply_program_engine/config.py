import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "Structural Panel Supply Program Engine"
    ENV: str = os.getenv("ENV", "dev")
    LEDGER_PATH: str = os.getenv("LEDGER_PATH", "data/ledger.jsonl")
    HMAC_SECRET: str = os.getenv("HMAC_SECRET", "dev-secret")
    LEDGER_BACKEND: str = os.getenv("LEDGER_BACKEND", "file")
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

settings = Settings()