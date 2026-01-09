#!/usr/bin/env bash
# mlx_runtime.sh — Apple Silicon MLX pack
# Installs MLX and MLX-LM for fast local inference
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:mlx_runtime] $*"; }
die(){ echo "[pack:mlx_runtime] ERROR: $*" >&2; exit 1; }

# Check for Apple Silicon
if [[ "$(uname -s)" != "Darwin" ]] || [[ "$(uname -m)" != "arm64" ]]; then
  log "WARN: MLX runtime is optimized for Apple Silicon (arm64)"
  log "      On other platforms, performance may be limited"
fi

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# pip packages
PIP_PACKAGES="mlx mlx-lm huggingface_hub"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install mlx_runtime pack"
  log "  Pip packages: $PIP_PACKAGES"
  exit 0
fi

log "Installing mlx_runtime pack..."

# Install pip packages
if [[ -f "$BASE_DIR/.venv/bin/pip3" ]]; then
  log "Installing pip3 packages..."
  # shellcheck disable=SC2086
  "$BASE_DIR/.venv/bin/pip3" install --quiet $PIP_PACKAGES
elif command -v pip3 >/dev/null 2>&1; then
  log "Installing pip3 packages (system)..."
  # shellcheck disable=SC2086
  pip3 install --quiet --user $PIP_PACKAGES
fi

# Create MLX models directory
mkdir -p "$MODELS_DIR/mlx"

# Update feature flag
features_yml="$BASE_DIR/config/features.yml"
if [[ -f "$features_yml" ]]; then
  if grep -q "^packs.mlx_runtime:" "$features_yml"; then
    sed -i '' 's/^packs.mlx_runtime:.*/packs.mlx_runtime: true/' "$features_yml"
  else
    echo "packs.mlx_runtime: true" >> "$features_yml"
  fi
fi

log "Pack installed!"
log "MLX models dir: $MODELS_DIR/mlx"
log ""
log "Quick test:"
log "  python3 -c 'import mlx; print(mlx.__version__)'"
log ""
log "Download a model:"
log "  mlx_lm.download --model mlx-community/Llama-3.2-1B-Instruct-4bit"
