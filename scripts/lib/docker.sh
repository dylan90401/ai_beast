#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/lib/ux.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/lib/deps.sh"

pick_runtime() {
  # If user set DOCKER_RUNTIME, respect it.
  if [[ "${DOCKER_RUNTIME:-}" == "colima" || "${DOCKER_RUNTIME:-}" == "docker" ]]; then
    echo "$DOCKER_RUNTIME"
    return 0
  fi

  # Default: Colima-first if present (macOS), else docker.
  if ensure_colima; then
    echo "colima"
  else
    echo "docker"
  fi
}

ensure_runtime_ready() {
  local rt
  rt="$(pick_runtime)"

  case "$rt" in
    colima)
      ux_info "Runtime: colima"
      have colima || die "colima not installed"
      # Start if not running
      if ! colima status >/dev/null 2>&1; then
        ux_info "Starting colima…"
        colima start --cpu 6 --memory 12 --disk 80 >/dev/null
      fi
      ;;
    docker)
      ux_info "Runtime: docker"
      ensure_docker_cli
      docker info >/dev/null 2>&1 || die "docker daemon not reachable (is Docker Desktop running?)"
      ;;
    *)
      die "Invalid runtime: $rt"
      ;;
  esac
}