from __future__ import annotations

from supply_program_engine.config import settings
from supply_program_engine.queue.base import QueueBackend, QueueUnavailableError, TaskMessage
from supply_program_engine.queue.redis_queue import RedisQueue
from supply_program_engine.queue.sync_queue import MEMORY_QUEUE

_QUEUE_BACKEND: QueueBackend | None = None


def get_queue() -> QueueBackend:
    global _QUEUE_BACKEND

    if _QUEUE_BACKEND is not None:
        return _QUEUE_BACKEND

    if settings.QUEUE_BACKEND == "redis":
        _QUEUE_BACKEND = RedisQueue(redis_url=settings.REDIS_URL, queue_name=settings.QUEUE_NAME)
        return _QUEUE_BACKEND

    _QUEUE_BACKEND = MEMORY_QUEUE
    return _QUEUE_BACKEND


def reset_queue_backend() -> None:
    global _QUEUE_BACKEND
    _QUEUE_BACKEND = None
    MEMORY_QUEUE.clear()


__all__ = ["TaskMessage", "QueueUnavailableError", "get_queue", "reset_queue_backend"]
