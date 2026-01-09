#!/usr/bin/env bash
# packs.sh — Pack management helpers
# AI Beast / Kryptos
#
# Packs are curated tool bundles defined in config/packs.json
# Each pack can include:
#   - Homebrew formulae and casks
#   - pip packages
#   - Docker extensions
#   - ComfyUI custom nodes
#   - Feature flags

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"
# shellcheck source=scripts/lib/deps.sh
[[ -f "$SCRIPT_LIB_DIR/deps.sh" ]] && source "$SCRIPT_LIB_DIR/deps.sh"

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

# Get packs config file path
packs_config_file() {
  echo "${BASE_DIR:-$(pwd)}/config/packs.json"
}

# Get packs scripts directory
packs_scripts_dir() {
  echo "${BASE_DIR:-$(pwd)}/scripts/packs"
}

# ─────────────────────────────────────────────────────────────
# JSON Helpers (requires jq)
# ─────────────────────────────────────────────────────────────

# Check if jq is available
packs_require_jq() {
  if ! command_exists jq; then
    log_error "jq is required for pack management"
    log_info "Install with: brew install jq"
    return 1
  fi
}

# Get pack property
packs_get_prop() {
  local pack="$1"
  local prop="$2"
  local config
  config="$(packs_config_file)"
  
  packs_require_jq || return 1
  [[ -f "$config" ]] || return 1
  
  jq -r ".packs[\"$pack\"].$prop // empty" "$config"
}

# Get pack array property
packs_get_array() {
  local pack="$1"
  local prop="$2"
  local config
  config="$(packs_config_file)"
  
  packs_require_jq || return 1
  [[ -f "$config" ]] || return 1
  
  jq -r ".packs[\"$pack\"].${prop}[]? // empty" "$config"
}

# ─────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────

# List all available packs
packs_list_all() {
  local config
  config="$(packs_config_file)"
  
  packs_require_jq || return 1
  [[ -f "$config" ]] || { log_warn "No packs config found"; return 1; }
  
  jq -r '.packs | keys[]' "$config" | sort
}

# Check if pack exists
packs_exists() {
  local pack="$1"
  local config
  config="$(packs_config_file)"
  
  packs_require_jq || return 1
  [[ -f "$config" ]] || return 1
  
  jq -e ".packs[\"$pack\"]" "$config" >/dev/null 2>&1
}

# Get pack description
packs_desc() {
  local pack="$1"
  packs_get_prop "$pack" "desc"
}

# Get pack dependencies
packs_deps() {
  local pack="$1"
  packs_get_array "$pack" "depends"
}

# ─────────────────────────────────────────────────────────────
# Installation Components
# ─────────────────────────────────────────────────────────────

# Get brew formulae for pack
packs_brew_formulae() {
  local pack="$1"
  packs_get_array "$pack" "brew.formulae"
}

# Get brew casks for pack
packs_brew_casks() {
  local pack="$1"
  packs_get_array "$pack" "brew.casks"
}

# Get pip packages for pack
packs_pip_packages() {
  local pack="$1"
  packs_get_array "$pack" "pip"
}

# Get docker extensions for pack
packs_docker_extensions() {
  local pack="$1"
  packs_get_array "$pack" "docker.extensions"
}

# Get comfyui nodes for pack
packs_comfyui_nodes() {
  local pack="$1"
  local config
  config="$(packs_config_file)"
  
  packs_require_jq || return 1
  [[ -f "$config" ]] || return 1
  
  jq -r ".packs[\"$pack\"].comfyui_nodes[]?.repo // empty" "$config"
}

# ─────────────────────────────────────────────────────────────
# Installation
# ─────────────────────────────────────────────────────────────

# Install pack dependencies (brew)
packs_install_brew() {
  local pack="$1"
  
  local formulae
  formulae=$(packs_brew_formulae "$pack")
  local casks
  casks=$(packs_brew_casks "$pack")
  
  if [[ -n "$formulae" ]]; then
    log_info "Installing brew formulae for $pack..."
    # shellcheck disable=SC2086
    deps_brew_install_formulae $formulae
  fi
  
  if [[ -n "$casks" ]]; then
    log_info "Installing brew casks for $pack..."
    # shellcheck disable=SC2086
    deps_brew_install_casks $casks
  fi
}

# Install pack dependencies (pip)
packs_install_pip() {
  local pack="$1"
  local venv="${2:-}"
  
  local packages
  packages=$(packs_pip_packages "$pack")
  
  if [[ -z "$packages" ]]; then
    return 0
  fi
  
  log_info "Installing pip packages for $pack..."
  
  local pip_cmd="pip3"
  if [[ -n "$venv" && -f "$venv/bin/pip3" ]]; then
    pip_cmd="$venv/bin/pip3"
  elif [[ -n "$venv" && -f "$venv/bin/pip" ]]; then
    pip_cmd="$venv/bin/pip"
  fi
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would install: $packages"
    return 0
  fi
  
  echo "$packages" | xargs "$pip_cmd" install --quiet
}

# Install pack docker extensions
packs_install_extensions() {
  local pack="$1"
  
  local extensions
  extensions=$(packs_docker_extensions "$pack")
  
  if [[ -z "$extensions" ]]; then
    return 0
  fi
  
  log_info "Enabling docker extensions for $pack..."
  
  # shellcheck source=scripts/lib/extensions.sh
  source "$SCRIPT_LIB_DIR/extensions.sh"
  
  for ext in $extensions; do
    if ext_exists "$ext"; then
      ext_enable "$ext"
    else
      log_warn "Extension not found: $ext"
    fi
  done
}

# Run pack-specific install script if exists
packs_run_script() {
  local pack="$1"
  local script_dir
  script_dir="$(packs_scripts_dir)"
  local script="$script_dir/${pack}.sh"
  
  if [[ ! -f "$script" ]]; then
    return 0
  fi
  
  log_info "Running pack script: $script"
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would run: bash $script --apply"
    return 0
  fi
  
  bash "$script" --apply
}

# Install a complete pack with all dependencies
packs_install() {
  local pack="$1"
  
  if ! packs_exists "$pack"; then
    log_error "Pack not found: $pack"
    return 1
  fi
  
  log_info "Installing pack: $pack"
  log_info "  Description: $(packs_desc "$pack")"
  
  # Install dependencies first
  local deps
  deps=$(packs_deps "$pack")
  if [[ -n "$deps" ]]; then
    log_info "  Dependencies: $deps"
    for dep in $deps; do
      if packs_exists "$dep"; then
        packs_install "$dep"
      fi
    done
  fi
  
  # Install components
  packs_install_brew "$pack"
  packs_install_pip "$pack"
  packs_install_extensions "$pack"
  packs_run_script "$pack"
  
  # Update features.env
  packs_set_feature "$pack" true
  
  log_success "Pack installed: $pack"
}

# ─────────────────────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────────────────────

# Set pack feature flag in features.yml
packs_set_feature() {
  local pack="$1"
  local value="$2"
  local features_file="${BASE_DIR:-$(pwd)}/config/features.yml"
  
  if [[ ! -f "$features_file" ]]; then
    return 0
  fi
  
  local key="packs.${pack}"
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would set $key: $value in features.yml"
    return 0
  fi
  
  # Update or add the feature flag
  if grep -q "^${key}:" "$features_file"; then
    sed -i '' "s/^${key}:.*/${key}: ${value}/" "$features_file"
  else
    echo "${key}: ${value}" >> "$features_file"
  fi
}

# ─────────────────────────────────────────────────────────────
# Info
# ─────────────────────────────────────────────────────────────

# Show pack details
packs_info() {
  local pack="$1"
  
  if ! packs_exists "$pack"; then
    log_error "Pack not found: $pack"
    return 1
  fi
  
  echo "Pack: $pack"
  echo "  Description: $(packs_desc "$pack")"
  
  local deps
  deps=$(packs_deps "$pack")
  [[ -n "$deps" ]] && echo "  Dependencies: $deps"
  
  local formulae
  formulae=$(packs_brew_formulae "$pack")
  [[ -n "$formulae" ]] && echo "  Brew formulae: $(echo "$formulae" | tr '\n' ' ')"
  
  local casks
  casks=$(packs_brew_casks "$pack")
  [[ -n "$casks" ]] && echo "  Brew casks: $(echo "$casks" | tr '\n' ' ')"
  
  local pip
  pip=$(packs_pip_packages "$pack")
  [[ -n "$pip" ]] && echo "  Pip packages: $(echo "$pip" | tr '\n' ' ')"
  
  local exts
  exts=$(packs_docker_extensions "$pack")
  [[ -n "$exts" ]] && echo "  Docker extensions: $(echo "$exts" | tr '\n' ' ')"
  
  local nodes
  nodes=$(packs_comfyui_nodes "$pack")
  [[ -n "$nodes" ]] && echo "  ComfyUI nodes: $(echo "$nodes" | wc -l | tr -d ' ') repos"
  
  local notes
  notes=$(packs_get_prop "$pack" "notes")
  [[ -n "$notes" ]] && echo "  Notes: $notes"
}

# List all packs with status
packs_list_status() {
  local features_file="${BASE_DIR:-$(pwd)}/config/features.yml"
  
  echo "Available Packs"
  echo "==============="
  
  for pack in $(packs_list_all); do
    local status="disabled"
    if [[ -f "$features_file" ]] && grep -q "^packs\.${pack}: true" "$features_file"; then
      status="enabled"
    fi
    printf "  %-25s [%-8s] %s\n" "$pack" "$status" "$(packs_desc "$pack" | cut -c1-50)"
  done
}
