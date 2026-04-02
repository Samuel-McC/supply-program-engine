from __future__ import annotations

import time

from supply_program_engine.enrichment import run_once as enrichment_run_once
from supply_program_engine.learning import run_once as learning_run_once
from supply_program_engine.logging import get_logger
from supply_program_engine.outbound.sender import run_once as sender_run_once
from supply_program_engine.queue import get_queue
from supply_program_engine.queue.base import TaskMessage

log = get_logger("supply_program_engine")


def dispatch_task(task: TaskMessage) -> dict[str, object]:
    limit = int(task.metadata.get("limit", 50))

    if task.task_type == "enrichment_run":
        result = enrichment_run_once(limit=limit)
    elif task.task_type == "sender_run":
        result = sender_run_once(limit=limit)
    elif task.task_type == "learning_run":
        result = learning_run_once(limit=limit)
    else:
        raise ValueError(f"unsupported_task_type:{task.task_type}")

    return {
        "task_type": task.task_type,
        "entity_id": task.entity_id,
        "correlation_id": task.correlation_id,
        "metadata": task.metadata,
        "runner_result": result,
    }


def run_once(timeout_seconds: int = 0) -> dict[str, object]:
    task = get_queue().dequeue(timeout_seconds=timeout_seconds)
    if task is None:
        return {"status": "idle"}

    result = dispatch_task(task)
    log.info(
        "worker_task_processed",
        extra={
            "task_type": task.task_type,
            "entity_id": task.entity_id,
            "correlation_id": task.correlation_id,
        },
    )
    return {"status": "processed", **result}


def serve_forever(poll_timeout_seconds: int = 5, sleep_seconds: float = 0.25) -> None:
    while True:
        result = run_once(timeout_seconds=poll_timeout_seconds)
        if result.get("status") == "idle":
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    serve_forever()
