#!/usr/bin/env bash
set -u

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"

mkdir -p "$RUN_DIR" "$LOG_DIR"
validate_ports

adopt_project_process() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  local url="$4"
  local pattern="$5"

  local pid
  pid="$(
    {
      project_listener_pids "$port"
      matching_project_pids "$pattern"
    } | unique_pids | head -n 1
  )"

  if [ -n "$pid" ]; then
    echo "$pid" >"$pid_file"
    echo "$name already running on $url with adopted PID $pid"
    return 0
  fi

  return 1
}

start_detached() {
  if command -v setsid >/dev/null 2>&1; then
    exec setsid "$@"
  fi

  exec nohup "$@"
}

start_backend() {
  if is_running_pid_file "$BACKEND_PID"; then
    echo "Backend already running on PID $(cat "$BACKEND_PID")"
    return
  fi

  rm -f "$BACKEND_PID"
  if port_in_use "$BACKEND_PORT"; then
    if adopt_project_process "Backend" "$BACKEND_PID" "$BACKEND_PORT" "$BACKEND_URL" "uvicorn app.main:app|uv run uvicorn"; then
      return
    fi
    echo "Backend port $BACKEND_PORT is already in use by a non-project process."
    echo "Change APP_BACKEND_PORT in .env or stop the process using this port."
    return
  fi

  (
    cd "$ROOT_DIR/backend" || exit 1
    export BACKEND_CORS_ORIGINS="[\"http://localhost:${FRONTEND_PORT}\",\"http://127.0.0.1:${FRONTEND_PORT}\"]"
    start_detached uv run uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
  ) >"$BACKEND_LOG" 2>&1 </dev/null &
  echo "$!" >"$BACKEND_PID"
  sleep 2

  if is_running_pid_file "$BACKEND_PID"; then
    echo "Backend started on $BACKEND_URL with PID $(cat "$BACKEND_PID")"
    echo "Backend log: logs/backend.log"
    return
  fi

  echo "Backend failed to start. Last log lines:"
  tail -n 20 "$BACKEND_LOG" 2>/dev/null || true
  rm -f "$BACKEND_PID"
}

start_frontend() {
  if is_running_pid_file "$FRONTEND_PID"; then
    echo "Frontend already running on PID $(cat "$FRONTEND_PID")"
    return
  fi

  rm -f "$FRONTEND_PID"
  if port_in_use "$FRONTEND_PORT"; then
    if adopt_project_process "Frontend" "$FRONTEND_PID" "$FRONTEND_PORT" "$FRONTEND_URL" "npm run dev|node .*vite|sh -c vite|vite .*--port"; then
      return
    fi
    echo "Frontend port $FRONTEND_PORT is already in use by a non-project process."
    echo "Change APP_FRONTEND_PORT in .env or stop the process using this port."
    return
  fi

  (
    cd "$ROOT_DIR/frontend" || exit 1
    export VITE_API_BASE_URL="${VITE_API_BASE_URL:-$BACKEND_URL}"
    start_detached npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort
  ) >"$FRONTEND_LOG" 2>&1 </dev/null &
  echo "$!" >"$FRONTEND_PID"
  sleep 2

  if is_running_pid_file "$FRONTEND_PID"; then
    echo "Frontend started on $FRONTEND_URL with PID $(cat "$FRONTEND_PID")"
    echo "Frontend log: logs/frontend.log"
    return
  fi

  echo "Frontend failed to start. Last log lines:"
  tail -n 20 "$FRONTEND_LOG" 2>/dev/null || true
  rm -f "$FRONTEND_PID"
}

start_backend
start_frontend
