#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"

require_docker_compose

mkdir -p "$RUN_DIR" "$LOG_DIR"
ensure_root_env
validate_ports
prepare_docker_runs_dir

(cd "$ROOT_DIR" && docker compose build)

set_deploy_mode docker

echo "Docker setup completed."
echo "Deployment mode: docker"
echo "Run make up to start backend and frontend with Docker Compose."
echo "Run artifacts are persisted in backend/runs via the Docker volume mount."
echo "Edit .env with provider keys before running live analysis."
