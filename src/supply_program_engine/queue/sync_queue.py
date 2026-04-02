from __future__ import annotations

from collections import deque

from supply_program_engine import ledger
from supply_program_engine.queue.base import QueueBackend, TaskMessage


class MemoryQueue(QueueBackend):
    def __init__(self) -> None:
        self._items: deque[str] = deque()

    def enqueue(self, task: TaskMessage) -> dict[str, object]:
        self._items.append(task.model_dump_json())
        return {
            "status": "enqueued",
            "task_id": ledger.generate_event_id(task.model_dump()),
            "task_type": task.task_type,
            "queue_depth": len(self._items),
        }

    def dequeue(self, timeout_seconds: int = 0) -> TaskMessage | None:
        if not self._items:
            return None
        return TaskMessage.model_validate_json(self._items.popleft())

    def clear(self) -> None:
        self._items.clear()


MEMORY_QUEUE = MemoryQueue()
