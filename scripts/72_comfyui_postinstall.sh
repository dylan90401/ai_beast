#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

log(){ echo "[comfy-post] $*"; }
die(){ echo "[comfy-post] ERROR: $*" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"
# Workflows dir (prefer ComfyUI user workflows)
COMFYUI_WORKFLOWS_DIR="${COMFYUI_WORKFLOWS_DIR:-$COMFYUI_DIR/user/default/workflows}"
mkdir -p "$COMFYUI_WORKFLOWS_DIR" || true


[[ -d "${COMFYUI_DIR:-}" ]] || die "COMFYUI_DIR not found: ${COMFYUI_DIR:-}"
[[ -n "${COMFYUI_MODELS_DIR:-}" ]] || die "COMFYUI_MODELS_DIR not set"

ensure_dir(){
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would mkdir -p "$1""
  else
    mkdir -p "$1"
  fi
}

link_models_dir(){
  local target="$COMFYUI_DIR/models"
  local src="$COMFYUI_MODELS_DIR"

  ensure_dir "$(dirname "$src")"
  ensure_dir "$src"

  if [[ -L "$target" ]]; then
    log "models already symlinked: $target -> $(readlink "$target")"
    return 0
  fi

  if [[ -d "$target" && "$(ls -A "$target" 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]]; then
    local backup="$target.backup_$(date +%Y%m%d_%H%M%S)"
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would move existing models dir to $backup"
    else
      mv "$target" "$backup"
      log "Backed up existing models dir: $backup"
    fi
  fi

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would ln -s "$src" "$target""
  else
    rm -rf "$target" 2>/dev/null || true
    ln -s "$src" "$target"
    log "Linked: $target -> $src"
  fi
}

seed_subdirs(){
  for d in checkpoints loras vae controlnet embeddings upscale_models clip clip_vision; do
    ensure_dir "$COMFYUI_MODELS_DIR/$d"
  done
}

main(){
  log "ComfyUI: $COMFYUI_DIR"
  log "ComfyUI models root: $COMFYUI_MODELS_DIR"
  seed_subdirs
  link_models_dir
  "$BASE_DIR/scripts/70_workflows_install.sh" "${@:-}" || true
  log "Done."
}

main "$@"

# Seed workflow templates if present
templates_dir="$BASE_DIR/workflows/templates"
if [[ -d "$templates_dir" ]]; then
  if [[ "$APPLY" -ne 1 ]]; then
    echo "[comfy-post] DRYRUN would seed workflow templates -> $COMFYUI_WORKFLOWS_DIR"
  else
    cp -n "$templates_dir"/*.json "$COMFYUI_WORKFLOWS_DIR"/ 2>/dev/null || true
  fi
fi
