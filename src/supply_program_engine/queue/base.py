from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


TaskType = Literal["enrichment_run", "sender_run", "learning_run"]


class QueueUnavailableError(RuntimeError):
    pass


class TaskMessage(BaseModel):
    task_type: TaskType
    entity_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class QueueBackend(ABC):
    @abstractmethod
    def enqueue(self, task: TaskMessage) -> dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def dequeue(self, timeout_seconds: int = 0) -> TaskMessage | None:
        raise NotImplementedError
