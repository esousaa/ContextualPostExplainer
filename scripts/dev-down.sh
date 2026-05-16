#!/usr/bin/env bash
set -u

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"
validate_ports

collect_service_pids() {
  local pid_file="$1"
  local port="$2"
  local pattern="$3"

  {
    if [ -f "$pid_file" ] && is_running_pid "$(cat "$pid_file")"; then
      cat "$pid_file"
    fi
    project_listener_pids "$port"
    matching_project_pids "$pattern"
  } | unique_pids
}

stop_pid() {
  local pid="$1"

  pkill -TERM -P "$pid" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
}

force_stop_pid_if_needed() {
  local pid="$1"

  if is_running_pid "$pid"; then
    pkill -KILL -P "$pid" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

stop_service() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  local pattern="$4"

  local pids
  pids="$(collect_service_pids "$pid_file" "$port" "$pattern")"

  if [ -n "$pids" ]; then
    while read -r pid; do
      stop_pid "$pid"
    done <<<"$pids"

    sleep 1

    while read -r pid; do
      force_stop_pid_if_needed "$pid"
    done <<<"$pids"

    echo "$name stopped"
  else
    echo "$name was not running as a project process"
  fi

  rm -f "$pid_file"
}

stop_service "Backend" "$BACKEND_PID" "$BACKEND_PORT" "uvicorn app.main:app|uv run uvicorn"
stop_service "Frontend" "$FRONTEND_PID" "$FRONTEND_PORT" "npm run dev|node .*vite|sh -c vite|vite .*--port"
