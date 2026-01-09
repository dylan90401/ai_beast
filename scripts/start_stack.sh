#!/usr/bin/env bash
set -euo pipefail
# start_stack.sh — helper to bring up the full stack with cleanup and port conflict handling
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
cd "$BASE_DIR"
CLEAN_CONTAINERS=1 KILL_PORT_CONFLICTS=1 ./bin/beast up --apply "$@"
