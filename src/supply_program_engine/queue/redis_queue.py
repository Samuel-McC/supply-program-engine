from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from supply_program_engine import ledger
from supply_program_engine.queue.base import QueueBackend, QueueUnavailableError, TaskMessage


@dataclass(frozen=True)
class RedisConnectionConfig:
    host: str
    port: int
    db: int
    password: str | None = None


def _parse_redis_url(redis_url: str) -> RedisConnectionConfig:
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        raise QueueUnavailableError("unsupported_redis_scheme")

    db_path = parsed.path.lstrip("/") or "0"
    return RedisConnectionConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        db=int(db_path),
        password=parsed.password,
    )


def _encode_command(*parts: str) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
    for part in parts:
        encoded = part.encode("utf-8")
        chunks.append(f"${len(encoded)}\r\n".encode("utf-8"))
        chunks.append(encoded + b"\r\n")
    return b"".join(chunks)


class _RedisProtocol:
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._reader = sock.makefile("rb")

    def execute(self, *parts: str):
        self._sock.sendall(_encode_command(*parts))
        return self._read_response()

    def _read_response(self):
        prefix = self._reader.read(1)
        if not prefix:
            raise QueueUnavailableError("redis_connection_closed")

        line = self._reader.readline().rstrip(b"\r\n")

        if prefix == b"+":
            return line.decode("utf-8")
        if prefix == b"-":
            raise QueueUnavailableError(line.decode("utf-8"))
        if prefix == b":":
            return int(line)
        if prefix == b"$":
            length = int(line)
            if length == -1:
                return None
            data = self._reader.read(length)
            self._reader.read(2)
            return data.decode("utf-8")
        if prefix == b"*":
            length = int(line)
            if length == -1:
                return None
            return [self._read_response() for _ in range(length)]

        raise QueueUnavailableError("unsupported_redis_response")


class RedisQueue(QueueBackend):
    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._connection = _parse_redis_url(redis_url)
        self._queue_name = queue_name

    def _client(self) -> _RedisProtocol:
        try:
            sock = socket.create_connection((self._connection.host, self._connection.port), timeout=2.0)
        except OSError as exc:
            raise QueueUnavailableError(str(exc)) from exc

        protocol = _RedisProtocol(sock)
        try:
            if self._connection.password:
                protocol.execute("AUTH", self._connection.password)
            if self._connection.db:
                protocol.execute("SELECT", str(self._connection.db))
            return protocol
        except Exception:
            sock.close()
            raise

    def enqueue(self, task: TaskMessage) -> dict[str, object]:
        protocol = self._client()
        try:
            queue_depth = protocol.execute("RPUSH", self._queue_name, task.model_dump_json())
        finally:
            protocol._sock.close()

        return {
            "status": "enqueued",
            "task_id": ledger.generate_event_id(task.model_dump()),
            "task_type": task.task_type,
            "queue_depth": int(queue_depth),
        }

    def dequeue(self, timeout_seconds: int = 0) -> TaskMessage | None:
        protocol = self._client()
        try:
            if timeout_seconds > 0:
                response = protocol.execute("BLPOP", self._queue_name, str(timeout_seconds))
                if response is None:
                    return None
                payload = response[1]
            else:
                payload = protocol.execute("LPOP", self._queue_name)
                if payload is None:
                    return None
        finally:
            protocol._sock.close()

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            return TaskMessage.model_validate_json(payload)

        return TaskMessage.model_validate(json.loads(payload))
