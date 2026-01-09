#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export BASE_DIR

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

parse_common_flags "${@:-}"

log_info "==> AI Beast Upgrade"
log_info "    BASE_DIR: $BASE_DIR"
log_info "    MODE: $(mode_label)"

confirm_apply "Upgrade workspace dependencies and runtimes" || exit 0

load_beast_config

log_info "[1/5] Updating git workspace..."
if [[ -d "$BASE_DIR/.git" ]]; then
  if [[ -n "$(git -C "$BASE_DIR" status --porcelain)" ]]; then
    log_warn "Working tree has changes; skipping git pull."
  else
    try_run git -C "$BASE_DIR" fetch --all --prune
    upstream="$(git -C "$BASE_DIR" rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>/dev/null || true)"
    if [[ -n "$upstream" ]]; then
      run git -C "$BASE_DIR" pull --ff-only
    else
      log_warn "No upstream tracking branch; skipping git pull."
    fi
  fi
else
  log_warn "No git repo found; skipping git update."
fi

log_info "[2/5] Updating Homebrew..."
if is_macos && command_exists brew; then
  try_run brew update
  try_run brew upgrade
  try_run brew cleanup
else
  log_warn "Homebrew not available; skipping brew updates."
fi

log_info "[3/5] Updating Python dependencies..."
VENV_PATH=""
if [[ -n "${VENV_DIR:-}" && -d "$VENV_DIR" ]]; then
  VENV_PATH="$VENV_DIR"
elif [[ -d "$BASE_DIR/.venv" ]]; then
  VENV_PATH="$BASE_DIR/.venv"
fi

if [[ -n "$VENV_PATH" ]]; then
  run /bin/bash -lc "source \"$VENV_PATH/bin/activate\" && python -m pip install -U pip wheel setuptools"
  if [[ -f "$BASE_DIR/requirements.txt" ]]; then
    run /bin/bash -lc "source \"$VENV_PATH/bin/activate\" && python -m pip install -r \"$BASE_DIR/requirements.txt\""
  fi
  if [[ -f "$BASE_DIR/requirements-dev.txt" ]]; then
    run /bin/bash -lc "source \"$VENV_PATH/bin/activate\" && python -m pip install -r \"$BASE_DIR/requirements-dev.txt\""
  fi
else
  log_warn "No virtualenv found; skipping pip updates."
fi

log_info "[4/5] Updating ComfyUI repos..."
if [[ -n "${COMFYUI_DIR:-}" && -d "$COMFYUI_DIR/.git" ]]; then
  if [[ -n "$(git -C "$COMFYUI_DIR" status --porcelain)" ]]; then
    log_warn "ComfyUI repo dirty; skipping pull."
  else
    try_run git -C "$COMFYUI_DIR" fetch --all --prune
    run git -C "$COMFYUI_DIR" pull --ff-only
  fi
else
  log_warn "COMFYUI_DIR not set or not a git repo; skipping."
fi

if [[ -n "${COMFYUI_DIR:-}" ]]; then
  MANAGER_DIR="$COMFYUI_DIR/custom_nodes/ComfyUI-Manager"
  if [[ -d "$MANAGER_DIR/.git" ]]; then
    if [[ -n "$(git -C "$MANAGER_DIR" status --porcelain)" ]]; then
      log_warn "ComfyUI-Manager repo dirty; skipping pull."
    else
      try_run git -C "$MANAGER_DIR" fetch --all --prune
      run git -C "$MANAGER_DIR" pull --ff-only
    fi
  fi
fi

log_info "[5/5] Updating docker images..."
if command_exists docker && [[ -f "$BASE_DIR/docker-compose.yml" ]]; then
  if docker info >/dev/null 2>&1; then
    run docker compose -f "$BASE_DIR/docker-compose.yml" pull
  else
    log_warn "Docker not running; skipping pull."
  fi
else
  log_warn "docker-compose.yml missing or docker not installed; skipping pull."
fi

log_success "Upgrade complete."
