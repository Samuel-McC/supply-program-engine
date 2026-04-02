import json
import logging
import uuid
from datetime import datetime, timezone

from supply_program_engine.observability import current_trace_ids

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id

        trace_ids = current_trace_ids()
        if trace_ids:
            log_record.update(trace_ids)

        return json.dumps(log_record)

def generate_correlation_id() -> str:
    return str(uuid.uuid4())
