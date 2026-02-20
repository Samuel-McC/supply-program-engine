import json
import os
from hashlib import sha256
from supply_program_engine.config import settings


def _ensure_file():
    os.makedirs(os.path.dirname(settings.LEDGER_PATH), exist_ok=True)
    if not os.path.exists(settings.LEDGER_PATH):
        open(settings.LEDGER_PATH, "w").close()


def append(event: dict):
    _ensure_file()
    with open(settings.LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def exists(event_id: str) -> bool:
    _ensure_file()
    with open(settings.LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("event_id") == event_id:
                return True
    return False


def generate_event_id(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True)
    return sha256(normalized.encode()).hexdigest()