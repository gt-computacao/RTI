#!/usr/bin/env bash
# Executado pelo systemd de usuário (~/.config/systemd/user/rpi.service).
# Só carrega o .env e sobe a API. Setup (venv, banco, seeds) é o setup-linux.sh.
set -euo pipefail
cd "${HOME}/project"
set -a
# shellcheck disable=SC1091
source .env
set +a
exec .venv/bin/uvicorn app.main:app \
  --host "${APP_HOST:-0.0.0.0}" \
  --port "${APP_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
