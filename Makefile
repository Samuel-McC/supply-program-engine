PYTHON ?= ./.venv/bin/python
UV ?= uv
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8000

.PHONY: help venv install run test db-upgrade demo-seed docker-up docker-down docker-demo-seed

help:
	@printf "%s\n" \
		"venv              Create the local virtual environment" \
		"install           Create the venv and install dependencies" \
		"run               Start the app locally with reload" \
		"test              Run the full pytest suite" \
		"db-upgrade        Run Alembic migrations for DB ledger mode" \
		"demo-seed         Seed a deterministic demo dataset locally" \
		"docker-up         Build and start the Docker demo stack" \
		"docker-down       Stop the Docker demo stack" \
		"docker-demo-seed  Seed the running Docker demo stack"

venv:
	$(UV) venv

install: venv
	$(UV) pip install -r requirements.txt

run:
	PYTHONPATH=src $(PYTHON) -m uvicorn supply_program_engine.api:app --app-dir src --host $(APP_HOST) --port $(APP_PORT) --reload

test:
	$(PYTHON) -m pytest -q

db-upgrade:
	PYTHONPATH=src $(PYTHON) -m supply_program_engine.db_migrations

demo-seed:
	PYTHONPATH=src $(PYTHON) -m supply_program_engine.demo_seed

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-demo-seed:
	docker compose exec app python -m supply_program_engine.demo_seed
