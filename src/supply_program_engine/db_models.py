from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, JSON, DateTime, func


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())