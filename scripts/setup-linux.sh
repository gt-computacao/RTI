#!/usr/bin/env bash
# Primeiro deploy (sem root). O systemd de usuário já existe e roda ~/start.sh
#
#   git clone <URL> ~/project
#   cd ~/project
#   cp .env.example .env && nano .env
#   ./scripts/setup-linux.sh
#   systemctl --user restart rpi.service
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "[setup] ERRO: não use sudo/root. Rode como o usuário do projeto (ex.: rpi)." >&2
  exit 1
fi

log() { echo "[setup] $*"; }
die() { echo "[setup] ERRO: $*" >&2; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME:-/etc/projects/rpi}"
UNIT_USER="${HOME_DIR}/.config/systemd/user/rpi.service"
DEST_START="${HOME_DIR}/start.sh"

[[ -f "$ROOT/app/main.py" && -f "$ROOT/requirements.txt" ]] \
  || die "rode de dentro do repositório clonado em ~/project"

command -v python3 >/dev/null 2>&1 || die "python3 não encontrado."
python3 -c "import venv" 2>/dev/null || die "módulo venv ausente (python3-venv)."

if [[ ! -f "$ROOT/.env" ]]; then
  [[ -f "$ROOT/.env.example" ]] || die "falta .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
  die "edite $ROOT/.env e rode de novo: $ROOT/scripts/setup-linux.sh"
fi

mkdir -p "$ROOT/storage/pdfs" "$ROOT/storage/author_documents" "$ROOT/storage/pi_files"
chmod 640 "$ROOT/.env" 2>/dev/null || true

stamp="$ROOT/.venv/.requirements-ok"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  log "criando venv..."
  python3 -m venv "$ROOT/.venv"
fi
if [[ ! -f "$stamp" || "$ROOT/requirements.txt" -nt "$stamp" ]]; then
  log "instalando dependências Python..."
  "$ROOT/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
  "$ROOT/.venv/bin/python" -m pip install --prefer-binary -r "$ROOT/requirements.txt"
  touch "$stamp"
fi

log "tabelas e seeds..."
"$ROOT/.venv/bin/alembic" upgrade head
"$ROOT/.venv/bin/python" "$ROOT/scripts/seed_catalogs.py"
"$ROOT/.venv/bin/python" "$ROOT/scripts/seed_admin.py"

cp "$ROOT/scripts/start.sh" "$DEST_START"
chmod +x "$DEST_START" "$ROOT/scripts/"*.sh
log "copiado $DEST_START"

if [[ -f "$UNIT_USER" ]]; then
  log "reiniciando systemd de usuário..."
  systemctl --user daemon-reload || true
  systemctl --user restart rpi.service
  sleep 2
  systemctl --user --no-pager --full status rpi.service || true
else
  log "aviso: não achei $UNIT_USER"
  log "depois: systemctl --user restart rpi.service"
fi

log "concluído."
log "status: systemctl --user status rpi.service"
log "logs:   journalctl --user -u rpi.service -f"
