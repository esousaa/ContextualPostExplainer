#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
ENV_FILE="$ROOT_DIR/.env"
DEPLOY_MODE_FILE="$RUN_DIR/deploy_mode"

env_value() {
  local key="$1"
  local default="$2"

  if [ -f "$ENV_FILE" ]; then
    local value
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)"
    value="${value%\"}"
    value="${value#\"}"
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return
    fi
  fi

  printf '%s' "$default"
}

BACKEND_PORT="$(env_value APP_BACKEND_PORT 8000)"
FRONTEND_PORT="$(env_value APP_FRONTEND_PORT 5173)"
BACKEND_URL="http://localhost:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

validate_port() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 1 ] || [ "$value" -gt 65535 ]; then
    echo "$name must be a valid TCP port. Current value: $value"
    exit 1
  fi
}

validate_ports() {
  validate_port "APP_BACKEND_PORT" "$BACKEND_PORT"
  validate_port "APP_FRONTEND_PORT" "$FRONTEND_PORT"
}

is_running_pid() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

is_running_pid_file() {
  local pid_file="$1"
  [ -f "$pid_file" ] && is_running_pid "$(cat "$pid_file")"
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1
    return $?
  fi

  python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    sys.exit(0)
finally:
    sock.close()
sys.exit(1)
PY
}

listener_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -t -iTCP:"$port" -sTCP:LISTEN -P -n 2>/dev/null || true
  fi
}

project_pid() {
  local pid="$1"
  [ -d "/proc/$pid" ] || return 1

  local cwd
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  if [[ "$cwd" == "$ROOT_DIR"* ]]; then
    return 0
  fi

  local cmdline
  cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$ROOT_DIR"* ]]
}

matching_project_pids() {
  local pattern="$1"
  {
    pgrep -f "$pattern" 2>/dev/null || true
  } | while read -r pid; do
    if project_pid "$pid"; then
      echo "$pid"
    fi
  done
}

project_listener_pids() {
  local port="$1"
  listener_pids "$port" | while read -r pid; do
    if project_pid "$pid"; then
      echo "$pid"
    fi
  done
}

unique_pids() {
  awk 'NF { seen[$1] = 1 } END { for (pid in seen) print pid }' | sort -n
}

ensure_root_env() {
  cd "$ROOT_DIR" || exit 1
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  fi
}

ensure_frontend_env() {
  cd "$ROOT_DIR" || exit 1
  if [ ! -f frontend/.env ]; then
    cp frontend/.env.example frontend/.env
    echo "Created frontend/.env from frontend/.env.example"
  fi
}

set_deploy_mode() {
  local mode="$1"
  mkdir -p "$RUN_DIR"
  printf '%s\n' "$mode" >"$DEPLOY_MODE_FILE"
}

read_deploy_mode() {
  if [ -f "$DEPLOY_MODE_FILE" ]; then
    tr -d '[:space:]' <"$DEPLOY_MODE_FILE"
  fi
}

require_deploy_mode() {
  local mode
  mode="$(read_deploy_mode)"
  case "$mode" in
    local|docker)
      printf '%s' "$mode"
      ;;
    *)
      echo "No deployment mode configured. Run make setup-local or make setup-docker first." >&2
      exit 1
      ;;
  esac
}

require_command() {
  local command_name="$1"
  local install_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$command_name is required. $install_hint"
    exit 1
  fi
}

require_docker_compose() {
  require_command docker "Install Docker before running make setup-docker."
  if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose is required. Install the Docker Compose plugin before running make setup-docker."
    exit 1
  fi
}

prepare_docker_runs_dir() {
  mkdir -p "$ROOT_DIR/backend/runs"
  chmod -R a+rwX "$ROOT_DIR/backend/runs"
}
