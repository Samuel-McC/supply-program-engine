import json
import os
from hashlib import sha256
from typing import Iterator, Optional


from supply_program_engine.config import settings



def _ensure_file() -> None:
    os.makedirs(os.path.dirname(settings.LEDGER_PATH), exist_ok=True)
    if not os.path.exists(settings.LEDGER_PATH):
        open(settings.LEDGER_PATH, "w", encoding="utf-8").close()




def _hash_record(record: dict) -> str:
    # hash only deterministic content
    material = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return sha256(material.encode("utf-8")).hexdigest()




def _compute_chain_hash(prev_hash: str, record: dict) -> str:
    # chain = hash(prev_hash + record_hash)
    record_hash = _hash_record(record)
    return sha256((prev_hash + record_hash).encode("utf-8")).hexdigest()




def last_hash() -> str:
    """
    Returns the last chain hash, or 'GENESIS' if ledger is empty.
    """
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
                # skip corrupt line
                continue
            if isinstance(rec, dict) and rec.get("hash"):
                last = rec["hash"]
    return last




def append(event: dict) -> dict:
    if getattr(settings, "LEDGER_BACKEND", "file") == "db":
        from supply_program_engine import ledger_db
        return ledger_db.append(event)
    return _append_file(event)


    # compute chain hash using prev + record-without-hash
    temp = dict(record)
    temp.pop("hash", None)
    record["hash"] = _compute_chain_hash(prev, temp)


    with open(settings.LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


    return record




def read(entity_id: Optional[str] = None):
    if getattr(settings, "LEDGER_BACKEND", "file") == "db":
        from supply_program_engine import ledger_db
        yield from ledger_db.read(entity_id=entity_id)
        return
    ...



def exists(event_id: str) -> bool:
    if getattr(settings, "LEDGER_BACKEND", "file") == "db":
        from supply_program_engine import ledger_db
        return ledger_db.exists(event_id)
    ...




def generate_event_id(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()




def find_by_entity(entity_id: str) -> list[dict]:
    return [rec for rec in read() if rec.get("entity_id") == entity_id]




def verify_chain() -> tuple[bool, Optional[str]]:
    """
    Verifies hash chain integrity.
    Returns (ok, error_message)
    """
    prev = "GENESIS"
    for rec in read():
        expected_prev = rec.get("prev_hash")
        if expected_prev != prev:
            return False, f"Broken chain: expected prev_hash={prev}, got {expected_prev}"


        # recompute
        temp = dict(rec)
        actual_hash = temp.pop("hash", None)
        computed = _compute_chain_hash(prev, temp)


        if actual_hash != computed:
            return False, "Tamper detected: hash mismatch"


        prev = actual_hash or prev


    return True, None


def get(event_id: str) -> Optional[dict]:
    if getattr(settings, "LEDGER_BACKEND", "file") == "db":
        from supply_program_engine import ledger_db
        return ledger_db.get(event_id)
    ...



def any_event_for_entity(entity_id: str, event_type: str) -> bool:
    """
    Returns True if an entity already has an event of a given type.
    Useful for "did we already send?" gates.
    """
    for rec in read():
        if rec.get("entity_id") == entity_id and rec.get("event_type") == event_type:
            return True
    return False