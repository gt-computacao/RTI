#!/usr/bin/env bash
set -e

echo "[entrypoint] Aguardando PostgreSQL em ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until nc -z "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}"; do
  sleep 1
done
echo "[entrypoint] PostgreSQL disponível."

echo "[entrypoint] Aplicando migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Seed catálogos e admin..."
python scripts/seed_catalogs.py
python scripts/seed_admin.py

RELOAD_FLAGS=""
case "${APP_ENV:-development}" in
  development|dev|local)
    echo "[entrypoint] Modo dev detectado (APP_ENV=${APP_ENV:-development}) — habilitando --reload."
    RELOAD_FLAGS="--reload --reload-dir /app/app --reload-dir /app/scripts"
    ;;
  *)
    echo "[entrypoint] Modo produção (APP_ENV=${APP_ENV}) — sem reload."
    ;;
esac

echo "[entrypoint] Iniciando Uvicorn..."
exec uvicorn app.main:app \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*" \
    ${RELOAD_FLAGS}
