#!/usr/bin/env bash
set -euo pipefail

# 33_logs.sh — tail logs for native or docker services.

svc="${1:-}"; shift || true
[[ -n "$svc" ]] || { echo "Usage: 33_logs.sh <service> [--tail N] [--follow]"; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"

parse_common_flags "${@:-}"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"
LOG_DIR="${LOG_DIR:-$BASE_DIR/logs}"

# lightweight arg parse
TAIL=200
FOLLOW=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail) TAIL="${2:-200}"; shift 2;;
    --no-follow) FOLLOW=0; shift;;
    --follow) FOLLOW=1; shift;;
    --apply|--dry-run|--verbose) shift;;
    *) shift;;
  esac
done

compose_args=()
if [[ -f "$BASE_DIR/docker-compose.yml" ]]; then
  compose_args=( -f "$BASE_DIR/docker-compose.yml" )
else
  compose_args=( -f "$BASE_DIR/docker/compose.yaml" -f "$BASE_DIR/docker/compose.ops.yaml" )
fi

# Native log handlers
native_tail(){
  local out="$1" err="${2:-}"
  [[ -f "$out" ]] || { echo "No log file: $out"; exit 2; }
  echo "== $out =="
  if [[ "$FOLLOW" -eq 1 ]]; then
    tail -n "$TAIL" -f "$out"
  else
    tail -n "$TAIL" "$out"
  fi

  if [[ -n "$err" ]]; then
    echo
    echo "== $err =="
    if [[ -f "$err" ]]; then
      if [[ "$FOLLOW" -eq 1 ]]; then
        tail -n "$TAIL" -f "$err"
      else
        tail -n "$TAIL" "$err"
      fi
    else
      echo "(missing)"
    fi
  fi
}

case "$svc" in
  comfyui)
    native_tail "$BASE_DIR/logs/comfyui.out.log" "$BASE_DIR/logs/comfyui.err.log"
    ;;

  speech_api|speech)
    native_tail "$LOG_DIR/speech_api.out.log" "$LOG_DIR/speech_api.err.log"
    ;;

  ollama)
    if pgrep -x ollama >/dev/null 2>&1; then
      echo "ollama: running (no file log; run: ollama ps / ollama logs not available)"
      exit 0
    fi
    echo "ollama: not running"
    exit 1
    ;;

  *)
    # Docker
    docker_runtime_is_ready || die "Docker runtime not ready (set DOCKER_RUNTIME and run: beast bootstrap)"

    if [[ "$FOLLOW" -eq 1 ]]; then
      docker compose "${compose_args[@]}" logs -f --tail "$TAIL" "$svc"
    else
      docker compose "${compose_args[@]}" logs --tail "$TAIL" "$svc"
    fi
    ;;
esac
