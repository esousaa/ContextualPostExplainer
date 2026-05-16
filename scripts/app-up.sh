#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"

mode="$(require_deploy_mode)"

case "$mode" in
  local)
    "$ROOT_DIR/scripts/dev-start.sh"
    ;;
  docker)
    require_docker_compose
    validate_ports
    ensure_root_env
    prepare_docker_runs_dir
    cd "$ROOT_DIR"
    docker compose up -d
    echo "Docker services started."
    echo "Frontend: $FRONTEND_URL"
    echo "Backend:  $BACKEND_URL"
    ;;
esac
