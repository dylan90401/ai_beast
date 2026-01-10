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
      if [[ "${DRYRUN:-1}" -eq 0 ]]; then
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
      if [[ "${DRYRUN:-1}" -eq 0 ]]; then
        log "Starting ComfyUI on ${AI_BEAST_BIND_ADDR:-127.0.0.1}:${port}"
        mkdir -p "$BASE_DIR/logs"
        nohup /bin/bash -lc "source \"$VENV_DIR/bin/activate\" && cd \"$COMFYUI_DIR\" && python main.py --listen ${AI_BEAST_BIND_ADDR:-127.0.0.1} --port ${port}" \
          >> "$BASE_DIR/logs/comfyui.out.log" 2>> "$BASE_DIR/logs/comfyui.err.log" &
      else
        log "DRYRUN: would start ComfyUI (python main.py --listen ... --port $port)"
      fi
    fi
  fi

  # Dashboard (best-effort)
  local dash_port="${PORT_DASHBOARD:-8787}"
  if ! pgrep -f "apps/dashboard/dashboard.py" >/dev/null 2>&1; then
    if [[ "${DRYRUN:-1}" -eq 0 ]]; then
      log "Starting dashboard on ${AI_BEAST_BIND_ADDR:-127.0.0.1}:${dash_port}"
      mkdir -p "$BASE_DIR/logs"
      nohup /bin/bash -lc "cd \"$BASE_DIR\" && python3 \"$BASE_DIR/apps/dashboard/dashboard.py\"" \
        >> "$BASE_DIR/logs/dashboard.out.log" 2>> "$BASE_DIR/logs/dashboard.err.log" &
    else
      log "DRYRUN: would start dashboard (apps/dashboard/dashboard.py)"
    fi
  fi
}

stop_native(){
  local port="${PORT_COMFYUI:-8188}"
  if [[ "${DRYRUN:-1}" -eq 0 ]]; then
    pkill -f "python .*main.py.*--port ${port}" >/dev/null 2>&1 || true
    pkill -f "apps/dashboard/dashboard.py" >/dev/null 2>&1 || true
  else
    log "DRYRUN: would pkill ComfyUI process (port=${port})"
    log "DRYRUN: would pkill dashboard process"
  fi
  # Leave ollama running by default.
}

ensure_compose_file(){
  # Prefer fully-generated compose (core + ops + enabled fragments)
  local out="$BASE_DIR/docker-compose.yml"
  local project="$BASE_DIR/kryptos_project.yml"
  local auto_gen="${AI_BEAST_COMPOSE_AUTO_GEN:-1}"
  if [[ "$auto_gen" == "1" && -f "$project" ]]; then
    if [[ "${DRYRUN:-1}" -eq 0 ]]; then
      "$BASE_DIR/scripts/25_compose_generate.sh" gen --apply --out="$out" >/dev/null
      echo "$out"; return 0
    fi
    log "DRYRUN: would generate $out from kryptos_project.yml"
    echo "$out"; return 0
  fi
  if [[ -f "$out" ]]; then
    echo "$out"; return 0
  fi

  # If we have extensions enabled or a state file, generate it.
  if find "$BASE_DIR/extensions" -type f -name enabled -print -quit 2>/dev/null | grep -q . || [[ -f "$BASE_DIR/config/state.json" ]]; then
    if [[ "${DRYRUN:-1}" -eq 0 ]]; then
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

  local cf; cf="$(ensure_compose_file)"
  local args=()
  local compose_files=()
  if [[ "$cf" == *";"* ]]; then
    IFS=';' read -r a b <<<"$cf"
    args=( -f "$a" -f "$b" )
    compose_files=( "$a" "$b" )
  else
    args=( -f "$cf" )
    compose_files=( "$cf" )
  fi

  mapfile -t profiles < <(python3 - "${compose_files[@]}" <<'PY'
import re
import sys

def parse_profiles(text):
    out=set()
    lines=text.splitlines()
    i=0
    while i < len(lines):
        line=lines[i]
        m=re.search(r'^\s*profiles:\s*\[(.*)\]\s*$', line)
        if m:
            body=m.group(1)
            for item in body.split(","):
                item=item.strip().strip("'\"")
                if item:
                    out.add(item)
            i += 1
            continue
        if re.search(r'^\s*profiles:\s*$', line):
            i += 1
            while i < len(lines) and re.search(r'^\s*-\s*', lines[i]):
                item=re.sub(r'^\s*-\s*', '', lines[i]).strip().strip("'\"")
                if item:
                    out.add(item)
                i += 1
            continue
        i += 1
    return out

profiles=set()
for path in sys.argv[1:]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            profiles |= parse_profiles(fh.read())
    except FileNotFoundError:
        continue

for p in sorted(profiles):
    print(p)
PY
)

if [[ "${#profiles[@]}" -eq 0 ]]; then
  log "No docker profiles found in compose file(s)."
else
  for p in "${profiles[@]}"; do args+=( --profile "$p" ); done
fi
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
