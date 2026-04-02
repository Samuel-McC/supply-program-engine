from __future__ import annotations

import argparse
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from supply_program_engine.config import settings
from supply_program_engine.logging import get_logger

log = get_logger("supply_program_engine")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def should_run_migrations() -> bool:
    return settings.LEDGER_BACKEND == "db"


def wait_for_database(max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (required for DB ledger backend).")

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            return
        except OperationalError as exc:
            last_error = exc
            log.warning(
                "database_not_ready",
                extra={"attempt": attempt, "max_attempts": max_attempts},
            )
            if attempt == max_attempts:
                break
            time.sleep(delay_seconds)

    raise RuntimeError("Database was not ready before migration startup deadline.") from last_error


def run_migrations() -> None:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (required for DB ledger backend).")

    alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(alembic_config, "head")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Alembic migrations for Supply Program Engine.")
    parser.add_argument("--retries", type=int, default=30, help="Maximum database readiness attempts.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between readiness attempts in seconds.")
    args = parser.parse_args(argv)

    if not should_run_migrations():
        log.info("database_migration_skipped", extra={"ledger_backend": settings.LEDGER_BACKEND})
        return 0

    wait_for_database(max_attempts=args.retries, delay_seconds=args.delay)
    run_migrations()
    log.info("database_migration_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
