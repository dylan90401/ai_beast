#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"

AI_BEAST_LOG_PREFIX="preflight"

parse_common_flags "${@:-}"
paths_env="$BASE_DIR/config/paths.env"
ports_env="$BASE_DIR/config/ports.env"
profiles_env="$BASE_DIR/config/profiles.env"

[[ -f "$paths_env" ]] || die "Missing $paths_env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$paths_env"
[[ -f "$ports_env" ]] && source "$ports_env" || true
[[ -f "$profiles_env" ]] && source "$profiles_env" || true
load_env_if_exists "$BASE_DIR/config/ai-beast.env"

is_darwin || warn "Non-macOS detected. Native bootstrap may not apply."

for c in bash git python3; do require_cmd "$c"; done

if have_cmd brew; then
  log "Homebrew: OK"
else
  warn "Homebrew: not installed (bootstrap can install with --apply)."
fi

if have_cmd docker; then
  log "Docker CLI: OK"
else
  warn "Docker CLI: not installed (fine if you only run native ComfyUI/Ollama)."
fi

# Docker runtime check (best-effort)
docker_runtime_ensure || true

# Ports check (best effort)
check_port(){
  local p="$1"; [[ -z "$p" ]] && return 0
  if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "PORT IN USE: $p"
  else
    log "Port free: $p"
  fi
}
log "Profile: ${AI_BEAST_PROFILE:-full}"
check_port "${PORT_DASHBOARD:-8787}"
check_port "${PORT_COMFYUI:-8188}"
check_port "${PORT_OLLAMA:-11434}"
check_port "${PORT_WEBUI:-3000}"
check_port "${PORT_QDRANT:-6333}"

df -h "$BASE_DIR" | sed 's/^/[preflight] /'
log "Preflight complete."
