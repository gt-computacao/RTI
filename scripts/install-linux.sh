#!/usr/bin/env bash
# Instalação completa no Linux (sem Docker): deps, PostgreSQL, banco, venv,
# systemd (enable + start) para subir no boot.
#
# Antes de rodar (como usuário normal; /opt é do root, por isso o chown):
#   sudo apt-get update && sudo apt-get install -y git
#   sudo mkdir -p /opt/rpi
#   sudo chown "$USER:$USER" /opt/rpi
#   cd /opt/rpi
#   git clone <URL-do-repositorio> .
#   cp .env.example .env && ${EDITOR:-nano} .env
#   # mínimo: SECRET_KEY, APP_BASE_URL, OAuth, e-mail, senha do Postgres
#   # produção: APP_ENV=production e APP_DEBUG=false
#   sudo ./scripts/install-linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERVICE_NAME="rpi"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

log() { echo "[install] $*"; }
die() { echo "[install] ERRO: $*" >&2; exit 1; }

need_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=""
    return
  fi
  command -v sudo >/dev/null 2>&1 || die "este script precisa de root ou sudo."
  sudo -n true 2>/dev/null || log "será pedida senha do sudo."
  SUDO="sudo"
}

resolve_app_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    APP_USER="$SUDO_USER"
  elif [[ "$(id -u)" -ne 0 ]]; then
    APP_USER="$(id -un)"
  else
    APP_USER="${RPI_SERVICE_USER:-rpi-app}"
    if ! id "$APP_USER" >/dev/null 2>&1; then
      log "criando usuário de serviço $APP_USER..."
      $SUDO useradd --system --home-dir "$ROOT" --chdir "$ROOT" --shell /usr/sbin/nologin "$APP_USER" \
        || $SUDO useradd --system --home-dir "$ROOT" --shell /usr/sbin/nologin "$APP_USER"
    fi
  fi
  APP_GROUP="$(id -gn "$APP_USER")"
  log "serviço irá rodar como ${APP_USER}:${APP_GROUP}"
}

as_app() {
  local cmd rootq
  cmd="$(printf '%q ' "$@")"
  rootq="$(printf '%q' "$ROOT")"
  if [[ "$(id -un)" == "$APP_USER" ]]; then
    bash -lc "cd ${rootq} && ${cmd}"
  elif [[ "$(id -u)" -eq 0 ]]; then
    runuser -u "$APP_USER" -- bash -lc "cd ${rootq} && ${cmd}"
  else
    sudo -u "$APP_USER" -H bash -lc "cd ${rootq} && ${cmd}"
  fi
}

as_pg() {
  if [[ "$(id -u)" -eq 0 ]]; then
    runuser -u postgres -- "$@"
  else
    sudo -u postgres "$@"
  fi
}

sql_ident_ok() {
  [[ "$1" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]
}

sql_quote() {
  local s="${1//\'/\'\'}"
  printf "%s" "$s"
}

require_project() {
  [[ -f "$ROOT/app/main.py" && -f "$ROOT/requirements.txt" ]] \
    || die "execute este script a partir do repositório clonado (faltam app/main.py ou requirements.txt)."
}

require_env() {
  if [[ -f "$ROOT/.env" ]]; then
    return
  fi
  [[ -f "$ROOT/.env.example" ]] || die "não há .env nem .env.example."
  cp "$ROOT/.env.example" "$ROOT/.env"
  log "criado $ROOT/.env a partir de .env.example."
  die "edite o .env (SECRET_KEY, APP_BASE_URL, OAuth, e-mail, senha Postgres; em produção APP_ENV=production e APP_DEBUG=false) e rode de novo: sudo $ROOT/scripts/install-linux.sh"
}

load_env() {
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
}

adapt_env_for_host() {
  local envf="$ROOT/.env"
  local host="${POSTGRES_HOST:-localhost}"
  if [[ "$host" == "db" ]]; then
    log "POSTGRES_HOST=db (Docker) — ajustando para localhost no .env."
    sed -i 's/^POSTGRES_HOST=.*/POSTGRES_HOST=localhost/' "$envf"
    sed -i 's/@db:/@localhost:/' "$envf"
  fi

  local pdf="${PDF_STORAGE_DIR:-}"
  if [[ -z "$pdf" || "$pdf" == /app/* ]]; then
    log "ajustando diretórios de storage para $ROOT/storage/..."
    if grep -q '^PDF_STORAGE_DIR=' "$envf"; then
      sed -i "s|^PDF_STORAGE_DIR=.*|PDF_STORAGE_DIR=$ROOT/storage/pdfs|" "$envf"
    else
      printf '\nPDF_STORAGE_DIR=%s/storage/pdfs\n' "$ROOT" >>"$envf"
    fi
    if grep -q '^AUTHOR_DOCUMENTS_STORAGE_DIR=' "$envf"; then
      sed -i "s|^AUTHOR_DOCUMENTS_STORAGE_DIR=.*|AUTHOR_DOCUMENTS_STORAGE_DIR=$ROOT/storage/author_documents|" "$envf"
    else
      printf 'AUTHOR_DOCUMENTS_STORAGE_DIR=%s/storage/author_documents\n' "$ROOT" >>"$envf"
    fi
    if grep -q '^PI_FILES_STORAGE_DIR=' "$envf"; then
      sed -i "s|^PI_FILES_STORAGE_DIR=.*|PI_FILES_STORAGE_DIR=$ROOT/storage/pi_files|" "$envf"
    else
      printf 'PI_FILES_STORAGE_DIR=%s/storage/pi_files\n' "$ROOT" >>"$envf"
    fi
  fi

  set -a
  # shellcheck disable=SC1091
  source "$envf"
  set +a

  POSTGRES_USER="${POSTGRES_USER:-rpi}"
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-rpi_password}"
  POSTGRES_DB="${POSTGRES_DB:-rpi}"
  POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
  POSTGRES_PORT="${POSTGRES_PORT:-5432}"
  APP_HOST="${APP_HOST:-0.0.0.0}"
  APP_PORT="${APP_PORT:-8000}"
}

install_apt_packages() {
  command -v apt-get >/dev/null 2>&1 || die "apenas Debian/Ubuntu (apt) são suportados neste script."

  log "atualizando apt e instalando pacotes (Python, WeasyPrint, PostgreSQL, git)..."
  $SUDO apt-get update -y
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    netcat-openbsd \
    postgresql \
    postgresql-contrib \
    postgresql-client
}

start_postgres() {
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now postgresql 2>/dev/null \
      || $SUDO systemctl enable --now postgresql.service 2>/dev/null \
      || true
  fi
  if command -v service >/dev/null 2>&1; then
    $SUDO service postgresql start 2>/dev/null || true
  fi

  log "aguardando PostgreSQL..."
  local i
  for i in $(seq 1 60); do
    if as_pg pg_isready -q 2>/dev/null || pg_isready -h 127.0.0.1 -p "${POSTGRES_PORT}" -q 2>/dev/null; then
      log "PostgreSQL disponível."
      return 0
    fi
    sleep 1
  done
  die "PostgreSQL não ficou pronto em 60s (systemctl status postgresql)."
}

ensure_role_and_db() {
  sql_ident_ok "$POSTGRES_USER" || die "POSTGRES_USER inválido: $POSTGRES_USER"
  sql_ident_ok "$POSTGRES_DB" || die "POSTGRES_DB inválido: $POSTGRES_DB"

  local pass_sql
  pass_sql="$(sql_quote "$POSTGRES_PASSWORD")"

  log "garantindo role e database (user=$POSTGRES_USER db=$POSTGRES_DB)..."
  as_pg psql -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
    CREATE ROLE ${POSTGRES_USER} LOGIN PASSWORD '${pass_sql}';
  ELSE
    ALTER ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${pass_sql}';
  END IF;
END
\$\$;
EOF

  local exists
  exists="$(as_pg psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'")"
  if [[ "$exists" != "1" ]]; then
    as_pg psql -v ON_ERROR_STOP=1 -c \
      "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER} ENCODING 'UTF8' TEMPLATE template0;"
  else
    log "database ${POSTGRES_DB} já existe — não será recriado."
    as_pg psql -v ON_ERROR_STOP=1 -c \
      "ALTER DATABASE ${POSTGRES_DB} OWNER TO ${POSTGRES_USER};" || true
  fi

  as_pg psql -v ON_ERROR_STOP=1 -d "$POSTGRES_DB" <<EOF
GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};
ALTER SCHEMA public OWNER TO ${POSTGRES_USER};
EOF
}

verify_tcp_login() {
  log "testando login TCP em 127.0.0.1:${POSTGRES_PORT}..."
  if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p "$POSTGRES_PORT" \
      -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT 1' >/dev/null; then
    die "falha de autenticação TCP como ${POSTGRES_USER}. Verifique pg_hba.conf."
  fi
  log "login TCP ok."
}

setup_python() {
  local py
  py="$(command -v python3)"
  [[ -n "$py" ]] || die "python3 não encontrado."

  $SUDO chown -R "${APP_USER}:${APP_GROUP}" "$ROOT"

  log "criando/atualizando venv em $ROOT/.venv (usuário $APP_USER)"
  as_app "$py" -m venv "$ROOT/.venv"
  as_app "$ROOT/.venv/bin/pip" install --upgrade pip
  as_app "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
}

migrate_and_seed() {
  log "migrations e seeds..."
  as_app "$ROOT/.venv/bin/alembic" upgrade head
  as_app "$ROOT/.venv/bin/python" "$ROOT/scripts/seed_catalogs.py"
  as_app "$ROOT/.venv/bin/python" "$ROOT/scripts/seed_admin.py"
}

write_unit() {
  command -v systemctl >/dev/null 2>&1 || die "systemd não encontrado — este instalador grava o serviço em ${UNIT_PATH}."

  log "gravando ${UNIT_PATH}..."
  $SUDO tee "$UNIT_PATH" >/dev/null <<EOF
[Unit]
Description=RPI IFMS — Registro de Propriedade Intelectual
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${ROOT}
EnvironmentFile=${ROOT}/.env
Environment=PYTHONUNBUFFERED=1
ExecStartPre=${ROOT}/.venv/bin/alembic upgrade head
ExecStartPre=${ROOT}/.venv/bin/python ${ROOT}/scripts/seed_catalogs.py
ExecStartPre=${ROOT}/.venv/bin/python ${ROOT}/scripts/seed_admin.py
ExecStart=${ROOT}/.venv/bin/uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT} --proxy-headers --forwarded-allow-ips=*
Restart=always
RestartSec=5
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF
}

enable_and_start() {
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable "${SERVICE_NAME}.service"
  $SUDO systemctl restart "${SERVICE_NAME}.service"
  sleep 2
  if ! $SUDO systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    $SUDO systemctl status --no-pager -l "${SERVICE_NAME}.service" || true
    $SUDO journalctl -u "${SERVICE_NAME}.service" -n 40 --no-pager || true
    die "serviço ${SERVICE_NAME} não ficou ativo. Veja os logs acima."
  fi
  log "serviço ${SERVICE_NAME} ativo e habilitado no boot."
}

fix_ownership() {
  $SUDO mkdir -p "$ROOT/storage/pdfs" "$ROOT/storage/author_documents" "$ROOT/storage/pi_files"
  $SUDO chown -R "${APP_USER}:${APP_GROUP}" \
    "$ROOT/storage" \
    "$ROOT/.venv" \
    "$ROOT/.env"
  $SUDO chmod 640 "$ROOT/.env"
  $SUDO chmod 750 "$ROOT/storage"
}

require_project
need_sudo
resolve_app_user
require_env
load_env
adapt_env_for_host
install_apt_packages
start_postgres
ensure_role_and_db
verify_tcp_login
setup_python
fix_ownership
migrate_and_seed
write_unit
enable_and_start

log "concluído."
log "status: sudo systemctl status ${SERVICE_NAME}"
log "logs:   sudo journalctl -u ${SERVICE_NAME} -f"
log "app:    http://127.0.0.1:${APP_PORT}  (ou o host da máquina, porta ${APP_PORT})"
log "parar:  sudo systemctl stop ${SERVICE_NAME}"
log "subir:  sudo systemctl start ${SERVICE_NAME}"
log "reiniciar após código/.env: sudo $ROOT/scripts/start-linux.sh"
if [[ "${APP_DEBUG:-true}" == "true" || "${APP_DEBUG:-}" == "1" ]]; then
  log "aviso: APP_DEBUG=${APP_DEBUG:-true} — /docs e modo debug ligados. Em produção use APP_DEBUG=false (APP_ENV sozinho não desliga)."
fi
