#!/usr/bin/env bash
# Reinicia o serviço systemd criado por scripts/install-linux.sh
# (use após alterar código ou .env — não há --reload neste fluxo)
set -euo pipefail
SERVICE_NAME="rpi"
if ! command -v systemctl >/dev/null 2>&1; then
  echo "[start] ERRO: systemd não encontrado. Rode: sudo ./scripts/install-linux.sh" >&2
  exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi
if [[ ! -f "/etc/systemd/system/${SERVICE_NAME}.service" ]]; then
  echo "[start] serviço ${SERVICE_NAME} ainda não existe. Rode: sudo ./scripts/install-linux.sh" >&2
  exit 1
fi
$SUDO systemctl restart "${SERVICE_NAME}.service"
$SUDO systemctl --no-pager --full status "${SERVICE_NAME}.service"
