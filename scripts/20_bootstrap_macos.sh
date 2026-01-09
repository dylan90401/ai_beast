#!/usr/bin/env bash
set -euo pipefail

# 20_bootstrap_macos.sh — installs macOS dependencies and prepares native runtimes.
# Refactored v17: all brew/pip plumbing lives in scripts/lib/deps.sh

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/deps.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/ux.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker.sh"

parse_common_flags "${@:-}"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
[[ -f "$BASE_DIR/config/ports.env" ]] || warn "Missing config/ports.env (will rely on defaults)"

# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"
load_env_if_exists "$BASE_DIR/config/ai-beast.env"

log "Target: macOS on Apple Silicon (expected)"

bootstrap_brew(){
  deps_ensure_homebrew || true
  deps_brew_update || true

  # Baseline tooling used across scripts
  deps_brew_install_formulae git jq yq coreutils gnu-sed gawk curl wget rsync

  # Python runtime/build
  deps_brew_install_formulae python

  # Optional: docker client + colima (only if runtime selection wants it)
  local rt; rt="$(docker_runtime_choice)"
  if [[ "$rt" == "colima" ]]; then
    deps_brew_install_formulae docker docker-compose colima
  fi
}

bootstrap_python_venv(){
  [[ -n "${VENV_DIR:-}" ]] || die "VENV_DIR not set (config/paths.env)"
  deps_python_venv_ensure "$VENV_DIR"
  deps_python_pip_upgrade "$VENV_DIR"

  # Optional bootstrap requirements for internal scripts (keep lightweight)
  local req="$BASE_DIR/scripts/requirements.txt"
  if [[ -f "$req" ]]; then
    deps_python_pip_install_requirements "$VENV_DIR" "$req"
  else
    log "No scripts/requirements.txt present; skipping pip deps."
  fi
}

bootstrap_dirs(){
  # Ensure canonical workspace subtrees exist (paths.env already points to them)
  for d in "$BASE_DIR/config/manifests" "$BASE_DIR/logs" "$BASE_DIR/docker/volumes"; do
    run mkdir -p "$d"
  done

  # Heavy storage directories
  for d in "$MODELS_DIR" "$DATA_DIR" "$OUTPUTS_DIR" "$BACKUP_DIR" "$LOG_DIR"; do
    run mkdir -p "$d"
  done
}

bootstrap_docker_runtime(){
  # Best-effort. For Docker Desktop, we only validate connectivity.
  docker_runtime_ensure || true
}

main(){
  log "Stage: brew tooling"
  bootstrap_brew

  log "Stage: directories"
  bootstrap_dirs

  log "Stage: python3 venv"
  bootstrap_python_venv

  log "Stage: docker runtime (best-effort)"
  bootstrap_docker_runtime

  log "Done. Next actions:"
  echo "  $BASE_DIR/bin/beast preflight"
  echo "  $BASE_DIR/bin/beast up --dry-run"
  echo "  $BASE_DIR/bin/beast up --apply"
}

main "$@"
