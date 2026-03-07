from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from supply_program_engine.config import settings

_engine: Engine | None = None
_SessionLocal = None


def get_engine() -> Engine:
    """
    Lazily create the SQLAlchemy engine.
    Only valid when DATABASE_URL is configured.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = getattr(settings, "DATABASE_URL", None)
    if not url:
        raise RuntimeError("DATABASE_URL is not set (required for DB ledger backend).")

    _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    engine = get_engine()
    _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal
