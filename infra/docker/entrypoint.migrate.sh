#!/usr/bin/env bash
set -euo pipefail
echo "Waiting for Postgres..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  sleep 1
done
echo "Running migrations..."
for f in /app/infra/database/migrations/*.sql; do
  [ -e "$f" ] || continue
  psql "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}" -f "$f"
done
exec "$@"
