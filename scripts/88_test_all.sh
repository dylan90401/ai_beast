#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: 88_test_all.sh [--no-docker]

Runs preflight, then:
  - With Docker available: make check
  - Without Docker: ruff, shellcheck, pytest
EOF
}

NO_DOCKER=0
for arg in "$@"; do
  case "$arg" in
    --no-docker) NO_DOCKER=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; usage; exit 1 ;;
  esac
done

run() {
  echo "+ $*"
  "$@"
}

cd "$BASE_DIR"
run ./bin/beast preflight --verbose

docker_ok=0
if [[ "$NO_DOCKER" -eq 0 ]] && command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    docker_ok=1
  fi
fi

if [[ "$docker_ok" -eq 1 ]]; then
  run make check
  exit 0
fi

echo "[test-all] Docker not available; running local checks."
run python3 -m ruff check .

if command -v shellcheck >/dev/null 2>&1; then
  run shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh
else
  echo "[test-all] shellcheck not installed; skipping."
fi

run python3 -m pytest -q
