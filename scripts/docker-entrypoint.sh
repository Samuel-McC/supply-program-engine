#!/bin/sh
set -eu

python -m supply_program_engine.db_migrations \
  --retries "${DB_MIGRATION_RETRIES:-30}" \
  --delay "${DB_MIGRATION_DELAY_SECONDS:-1}"

exec "$@"
