from supply_program_engine import db_migrations
from supply_program_engine.config import settings


def test_db_migrations_main_skips_for_file_backend(monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "file")

    assert db_migrations.main([]) == 0


def test_db_migrations_main_waits_and_runs_for_db_backend(monkeypatch):
    monkeypatch.setattr(settings, "LEDGER_BACKEND", "db")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://spe:spe_password@localhost:5432/spe")

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        db_migrations,
        "wait_for_database",
        lambda max_attempts, delay_seconds: calls.append(("wait", (max_attempts, delay_seconds))),
    )
    monkeypatch.setattr(db_migrations, "run_migrations", lambda: calls.append(("run", None)))

    assert db_migrations.main(["--retries", "5", "--delay", "0.25"]) == 0
    assert calls == [("wait", (5, 0.25)), ("run", None)]


def test_run_migrations_uses_project_alembic_config(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://spe:spe_password@localhost:5432/spe")

    captured: dict[str, object] = {}

    def fake_upgrade(config, revision):
        captured["url"] = config.get_main_option("sqlalchemy.url")
        captured["script_location"] = config.get_main_option("script_location")
        captured["revision"] = revision

    monkeypatch.setattr(db_migrations.command, "upgrade", fake_upgrade)

    db_migrations.run_migrations()

    assert captured["url"] == settings.DATABASE_URL
    assert str(captured["script_location"]).endswith("/alembic")
    assert captured["revision"] == "head"
