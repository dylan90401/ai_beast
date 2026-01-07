#!/usr/bin/env bash
set -euo pipefail

# 30_services.sh — start/stop native + docker services.

action="${1:-}"; shift || true
[[ -n "$action" ]] || { echo "Usage: 30_services.sh {up|down} [--dry-run|--apply] [--verbose]"; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"

AI_BEAST_LOG_PREFIX="services"
parse_common_flags "${@:-}"

paths_env="$BASE_DIR/config/paths.env"
[[ -f "$paths_env" ]] || die "Missing $paths_env (run: ./bin/beast init --apply)"

# shellcheck disable=SC1090
source "$paths_env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
[[ -f "$BASE_DIR/config/profiles.env" ]] && source "$BASE_DIR/config/profiles.env" || true
load_env_if_exists "$BASE_DIR/config/ai-beast.env"
load_env_if_exists "$BASE_DIR/config/features.env"

profile="${AI_BEAST_PROFILE:-full}"

start_native(){
  # Ollama (best-effort)
  if have_cmd ollama; then
    if ! pgrep -x ollama >/dev/null 2>&1; then
      if [[ "${APPLY:-0}" -eq 1 ]]; then
        log "Starting Ollama (ollama serve)"
        nohup ollama serve >/dev/null 2>&1 &
      else
        log "DRYRUN: would start ollama serve"
      fi
    fi
  fi

  # ComfyUI (best-effort)
  if [[ -n "${COMFYUI_DIR:-}" && -d "${COMFYUI_DIR:-}" && -n "${VENV_DIR:-}" && -d "${VENV_DIR:-}" ]]; then
    local port="${PORT_COMFYUI:-8188}"
    if ! pgrep -f "python .*main.py.*--port ${port}" >/dev/null 2>&1; then
      if [[ "${APPLY:-0}" -eq 1 ]]; then
        log "Starting ComfyUI on ${AI_BEAST_BIND_ADDR:-127.0.0.1}:${port}"
        mkdir -p "$BASE_DIR/logs"
        nohup /bin/bash -lc "source \"$VENV_DIR/bin/activate\" && cd \"$COMFYUI_DIR\" && python main.py --listen ${AI_BEAST_BIND_ADDR:-127.0.0.1} --port ${port}" \
          >> "$BASE_DIR/logs/comfyui.out.log" 2>> "$BASE_DIR/logs/comfyui.err.log" &
      else
        log "DRYRUN: would start ComfyUI (python main.py --listen ... --port $port)"
      fi
    fi
  fi
}

stop_native(){
  local port="${PORT_COMFYUI:-8188}"
  if [[ "${APPLY:-0}" -eq 1 ]]; then
    pkill -f "python .*main.py.*--port ${port}" >/dev/null 2>&1 || true
  else
    log "DRYRUN: would pkill ComfyUI process (port=${port})"
  fi
  # Leave ollama running by default.
}

ensure_compose_file(){
  # Prefer fully-generated compose (core + ops + enabled fragments)
  local out="$BASE_DIR/docker-compose.yml"
  if [[ -f "$out" ]]; then
    echo "$out"; return 0
  fi

  # If we have extensions enabled or a state file, generate it.
  if find "$BASE_DIR/extensions" -type f -name enabled -print -quit 2>/dev/null | grep -q . || [[ -f "$BASE_DIR/config/state.json" ]]; then
    if [[ "${APPLY:-0}" -eq 1 ]]; then
      "$BASE_DIR/scripts/25_compose_generate.sh" gen --apply --out="$out" >/dev/null
      echo "$out"; return 0
    fi
    log "DRYRUN: would generate $out (25_compose_generate.sh gen --apply)"
    # fall through
  fi

  # Fallback to static compose files
  echo "$BASE_DIR/docker/compose.yaml;$BASE_DIR/docker/compose.ops.yaml"
}

docker_up(){
  docker_runtime_ensure || { warn "Docker runtime not ready; skipping docker services"; return 0; }

  local profiles=()
  [[ "${FEATURE_DOCKER_QDRANT:-1}" -eq 1 ]] && profiles+=("qdrant")
  [[ "${FEATURE_DOCKER_OPEN_WEBUI:-1}" -eq 1 ]] && profiles+=("webui")
  [[ "${FEATURE_DOCKER_UPTIME_KUMA:-0}" -eq 1 ]] && profiles+=("kuma")
  [[ "${FEATURE_DOCKER_N8N:-0}" -eq 1 ]] && profiles+=("n8n")
  [[ "${FEATURE_DOCKER_SEARXNG:-0}" -eq 1 ]] && profiles+=("searxng")

  if [[ "${#profiles[@]}" -eq 0 ]]; then
    log "No docker profiles enabled (see config/features.yml)."
    return 0
  fi

  local cf; cf="$(ensure_compose_file)"
  local args=()
  if [[ "$cf" == *";"* ]]; then
    IFS=';' read -r a b <<<"$cf"
    args=( -f "$a" -f "$b" )
  else
    args=( -f "$cf" )
  fi

  for p in "${profiles[@]}"; do args+=( --profile "$p" ); done
  run docker compose "${args[@]}" up -d
}

docker_down(){
  docker_runtime_is_ready || return 0
  local cf; cf="$(ensure_compose_file)"
  local args=()
  if [[ "$cf" == *";"* ]]; then
    IFS=';' read -r a b <<<"$cf"
    args=( -f "$a" -f "$b" )
  else
    args=( -f "$cf" )
  fi
  run docker compose "${args[@]}" down
}

case "$action" in
  up)
    start_native
    if [[ "$profile" != "lite" ]]; then docker_up || true; fi
    ;;
  down)
    if [[ "$profile" != "lite" ]]; then docker_down || true; fi
    stop_native
    ;;
  *)
    die "Unknown action: $action"
    ;;
esac
