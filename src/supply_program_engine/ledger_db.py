
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import select

from supply_program_engine.db import get_sessionmaker
from supply_program_engine.db_models import Event


def _iso_timestamp(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _serialize_event(row: Event) -> dict:
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "entity_id": row.entity_id,
        "correlation_id": row.correlation_id,
        "payload": row.payload,
        "ts": _iso_timestamp(row.created_at),
    }


def append(event: dict) -> dict:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        db_event = Event(
            event_id=event["event_id"],
            event_type=event["event_type"],
            entity_id=event["entity_id"],
            correlation_id=event["correlation_id"],
            payload=event["payload"],
        )
        session.add(db_event)
        session.commit()
        session.refresh(db_event)
        return _serialize_event(db_event)


def exists(event_id: str) -> bool:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        stmt = select(Event.event_id).where(Event.event_id == event_id)
        return session.execute(stmt).scalar_one_or_none() is not None


def get(event_id: str) -> Optional[dict]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        stmt = select(Event).where(Event.event_id == event_id)
        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _serialize_event(row)


def read(entity_id: Optional[str] = None) -> Iterator[dict]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        stmt = select(Event).order_by(Event.created_at.asc())
        if entity_id:
            stmt = stmt.where(Event.entity_id == entity_id)

        for row in session.execute(stmt).scalars():
            yield _serialize_event(row)
