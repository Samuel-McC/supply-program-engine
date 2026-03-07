from __future__ import annotations

import json
import os
from hashlib import sha256
from typing import Iterator, Optional

from supply_program_engine.config import settings


def _use_db() -> bool:
    return getattr(settings, "LEDGER_BACKEND", "file") == "db"


def _ensure_file() -> None:
    ledger_dir = os.path.dirname(settings.LEDGER_PATH)
    if ledger_dir:
        os.makedirs(ledger_dir, exist_ok=True)

    if not os.path.exists(settings.LEDGER_PATH):
        open(settings.LEDGER_PATH, "w", encoding="utf-8").close()


def _hash_record(record: dict) -> str:
    material = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()


def _compute_chain_hash(prev_hash: str, record: dict) -> str:
    record_hash = _hash_record(record)
    return sha256((prev_hash + record_hash).encode("utf-8")).hexdigest()


def generate_event_id(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()


# -----------------------------
# FILE LEDGER HELPERS
# -----------------------------
def last_hash() -> str:
    _ensure_file()
    last = "GENESIS"

    with open(settings.LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(rec, dict) and rec.get("hash"):
                last = rec["hash"]

    return last


def _append_file(event: dict) -> dict:
    _ensure_file()

    prev = last_hash()
    record = dict(event)
    record["prev_hash"] = prev

    temp = dict(record)
    temp.pop("hash", None)
    record["hash"] = _compute_chain_hash(prev, temp)

    with open(settings.LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


def _read_file() -> Iterator[dict]:
    _ensure_file()

    with open(settings.LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(rec, dict):
                yield rec


# -----------------------------
# PUBLIC API
# -----------------------------
def append(event: dict) -> dict:
    if _use_db():
        from supply_program_engine import ledger_db
        return ledger_db.append(event)
    return _append_file(event)


def read(entity_id: Optional[str] = None) -> Iterator[dict]:
    if _use_db():
        from supply_program_engine import ledger_db
        yield from ledger_db.read(entity_id=entity_id)
        return

    if entity_id is None:
        yield from _read_file()
    else:
        for rec in _read_file():
            if rec.get("entity_id") == entity_id:
                yield rec


def exists(event_id: str) -> bool:
    if _use_db():
        from supply_program_engine import ledger_db
        return ledger_db.exists(event_id)

    for rec in _read_file():
        if rec.get("event_id") == event_id:
            return True
    return False


def get(event_id: str) -> Optional[dict]:
    if _use_db():
        from supply_program_engine import ledger_db
        return ledger_db.get(event_id)

    for rec in _read_file():
        if rec.get("event_id") == event_id:
            return rec
    return None


def find_by_entity(entity_id: str) -> list[dict]:
    return list(read(entity_id=entity_id))


def any_event_for_entity(entity_id: str, event_type: str) -> bool:
    for rec in read(entity_id=entity_id):
        if rec.get("event_type") == event_type:
            return True
    return False


def verify_chain() -> tuple[bool, Optional[str]]:
    """
    Only meaningful in file mode.
    In DB mode, return OK because DB ledger does not use file hash chaining.
    """
    if _use_db():
        return True, None

    prev = "GENESIS"

    for rec in _read_file():
        expected_prev = rec.get("prev_hash")
        if expected_prev != prev:
            return False, f"Broken chain: expected prev_hash={prev}, got {expected_prev}"

        temp = dict(rec)
        actual_hash = temp.pop("hash", None)
        computed = _compute_chain_hash(prev, temp)

        if actual_hash != computed:
            return False, "Tamper detected: hash mismatch"

        prev = actual_hash or prev

    return True, None
