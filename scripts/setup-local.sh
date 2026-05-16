#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-env.sh"

require_command uv "Install uv before running make setup-local."
require_command npm "Install Node.js/npm before running make setup-local."

mkdir -p "$RUN_DIR" "$LOG_DIR"
ensure_root_env
ensure_frontend_env

(cd "$ROOT_DIR/backend" && uv sync)
(cd "$ROOT_DIR/frontend" && npm install)

set_deploy_mode local

echo "Local setup completed."
echo "Deployment mode: local"
echo "Run make up to start backend and frontend."
echo "Edit .env with provider keys before running live analysis."
