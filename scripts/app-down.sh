#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"

mode="$(read_deploy_mode)"

stop_docker_stack_if_available() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    (cd "$ROOT_DIR" && docker compose down) || true
  fi
}

case "$mode" in
  local)
    "$ROOT_DIR/scripts/dev-down.sh"
    stop_docker_stack_if_available
    ;;
  docker)
    stop_docker_stack_if_available
    "$ROOT_DIR/scripts/dev-down.sh"
    ;;
  *)
    echo "No deployment mode configured. Trying to stop project-local processes."
    "$ROOT_DIR/scripts/dev-down.sh"
    stop_docker_stack_if_available
    ;;
esac
