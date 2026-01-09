#!/usr/bin/env bash
# config.sh — Configuration management helpers
# AI Beast / Kryptos
#
# Handles loading, validation, and manipulation of configuration files.

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"

# ─────────────────────────────────────────────────────────────
# Path Helpers
# ─────────────────────────────────────────────────────────────

# Get config directory
config_dir() {
  echo "${BASE_DIR:-$(pwd)}/config"
}

# Get specific config file path
config_file() {
  local name="$1"
  echo "$(config_dir)/$name"
}

# ─────────────────────────────────────────────────────────────
# Load Configuration
# ─────────────────────────────────────────────────────────────

# Load paths.env
config_load_paths() {
  local f
  f="$(config_file 'paths.env')"
  if [[ -f "$f" ]]; then
    # shellcheck source=/dev/null
    source "$f"
    return 0
  fi
  log_warn "paths.env not found. Run: ./bin/beast init --apply"
  return 1
}

# Load ports.env
config_load_ports() {
  local f
  f="$(config_file 'ports.env')"
  if [[ -f "$f" ]]; then
    # shellcheck source=/dev/null
    source "$f"
  fi
}

# Load features.env
config_load_features() {
  local f
  f="$(config_file 'features.env')"
  if [[ -f "$f" ]]; then
    # shellcheck source=/dev/null
    source "$f"
  fi
}

# Load profiles.env
config_load_profiles() {
  local f
  f="$(config_file 'profiles.env')"
  if [[ -f "$f" ]]; then
    # shellcheck source=/dev/null
    source "$f"
  fi
}

# Load all configuration
config_load_all() {
  config_load_paths || return 1
  config_load_ports
  config_load_features
  config_load_profiles
}

# ─────────────────────────────────────────────────────────────
# Feature Flag Helpers
# ─────────────────────────────────────────────────────────────

# Check if a feature is enabled (from features.yml or features.env)
config_feature_enabled() {
  local feature="$1"
  local features_env
  features_env="$(config_file 'features.env')"
  
  # Try features.env first (faster)
  if [[ -f "$features_env" ]]; then
    local var_name
    var_name=$(echo "$feature" | tr '.' '_' | tr '[:lower:]' '[:upper:]')
    local value
    value=$(grep "^${var_name}=" "$features_env" 2>/dev/null | cut -d= -f2 || true)
    [[ "$value" == "true" || "$value" == "1" ]] && return 0
  fi
  
  # Try features.yml
  local features_yml
  features_yml="$(config_file 'features.yml')"
  if [[ -f "$features_yml" ]]; then
    if grep -q "^${feature}: true" "$features_yml"; then
      return 0
    fi
  fi
  
  return 1
}

# Set a feature flag
config_feature_set() {
  local feature="$1"
  local value="$2"
  local features_yml
  features_yml="$(config_file 'features.yml')"
  
  if [[ ! -f "$features_yml" ]]; then
    log_warn "features.yml not found"
    return 1
  fi
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would set $feature: $value"
    return 0
  fi
  
  if grep -q "^${feature}:" "$features_yml"; then
    sed -i '' "s/^${feature}:.*/${feature}: ${value}/" "$features_yml"
  else
    echo "${feature}: ${value}" >> "$features_yml"
  fi
  
  log_info "Set feature: $feature = $value"
}

# ─────────────────────────────────────────────────────────────
# Profile Helpers
# ─────────────────────────────────────────────────────────────

# Get current profile
config_current_profile() {
  echo "${AI_BEAST_PROFILE:-full}"
}

# Set profile
config_set_profile() {
  local profile="$1"
  local profiles_env
  profiles_env="$(config_file 'profiles.env')"
  
  case "$profile" in
    lite|full|prodish)
      ;;
    *)
      log_error "Invalid profile: $profile (use: lite, full, prodish)"
      return 1
      ;;
  esac
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would set profile to: $profile"
    return 0
  fi
  
  echo "export AI_BEAST_PROFILE=\"$profile\"" > "$profiles_env"
  log_info "Profile set to: $profile"
}

# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────

# Validate all required config files exist
config_validate_required() {
  local missing_count=0
  
  for f in paths.env ports.env features.yml; do
    if [[ ! -f "$(config_file "$f")" ]]; then
      log_error "Missing required config: config/$f"
      missing_count=1
    fi
  done
  
  [[ $missing_count -eq 0 ]]
}

# Validate paths.env values
config_validate_paths() {
  config_load_paths || return 1
  
  local errors=0
  
  # Check BASE_DIR
  if [[ -z "${BASE_DIR:-}" ]]; then
    log_error "BASE_DIR not set in paths.env"
    errors=1
  elif [[ ! -d "$BASE_DIR" ]]; then
    log_warn "BASE_DIR does not exist: $BASE_DIR"
  fi
  
  # Check required paths exist or can be created
  for var in MODELS_DIR DATA_DIR OUTPUTS_DIR CACHE_DIR; do
    local val="${!var:-}"
    if [[ -z "$val" ]]; then
      log_warn "$var not set in paths.env"
    fi
  done
  
  [[ $errors -eq 0 ]]
}

# Validate ports.env for conflicts
config_validate_ports() {
  config_load_ports
  
  local -A seen_ports
  local conflicts=0
  
  # Get all PORT_ variables
  while IFS='=' read -r name value; do
    [[ "$name" == PORT_* ]] || continue
    value="${value//\"/}"
    
    if [[ -n "${seen_ports[$value]:-}" ]]; then
      log_error "Port conflict: $name and ${seen_ports[$value]} both use port $value"
      conflicts=1
    else
      seen_ports[$value]="$name"
    fi
  done < <(env | grep ^PORT_)
  
  [[ $conflicts -eq 0 ]]
}

# Run all validation
config_validate_all() {
  local errors=0
  
  log_info "Validating configuration..."
  
  config_validate_required || errors=1
  config_validate_paths || errors=1
  config_validate_ports || errors=1
  
  if [[ $errors -eq 0 ]]; then
    log_success "Configuration valid"
  else
    log_error "Configuration has errors"
  fi
  
  return $errors
}

# ─────────────────────────────────────────────────────────────
# State Management
# ─────────────────────────────────────────────────────────────

# Get state file path
config_state_file() {
  echo "$(config_dir)/state.json"
}

# Read state value (requires jq)
config_state_get() {
  local key="$1"
  local state_file
  state_file="$(config_state_file)"
  
  if [[ ! -f "$state_file" ]]; then
    return 1
  fi
  
  if ! command_exists jq; then
    log_warn "jq required for state management"
    return 1
  fi
  
  jq -r ".$key // empty" "$state_file"
}

# Set state value (requires jq)
config_state_set() {
  local key="$1"
  local value="$2"
  local state_file
  state_file="$(config_state_file)"
  
  if ! command_exists jq; then
    log_warn "jq required for state management"
    return 1
  fi
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would set state.$key = $value"
    return 0
  fi
  
  # Create or update state file
  if [[ -f "$state_file" ]]; then
    local tmp
    tmp=$(mktemp)
    jq ".$key = $value" "$state_file" > "$tmp"
    mv "$tmp" "$state_file"
  else
    echo "{\"$key\": $value}" > "$state_file"
  fi
}

# ─────────────────────────────────────────────────────────────
# Info/Debug
# ─────────────────────────────────────────────────────────────

# Show current configuration
config_show() {
  echo "AI Beast Configuration"
  echo "======================"
  echo ""
  
  echo "Profile: $(config_current_profile)"
  echo ""
  
  echo "Paths:"
  config_load_paths 2>/dev/null || true
  echo "  BASE_DIR: ${BASE_DIR:-<not set>}"
  echo "  MODELS_DIR: ${MODELS_DIR:-<not set>}"
  echo "  DATA_DIR: ${DATA_DIR:-<not set>}"
  echo "  OUTPUTS_DIR: ${OUTPUTS_DIR:-<not set>}"
  echo "  CACHE_DIR: ${CACHE_DIR:-<not set>}"
  echo "  COMFYUI_DIR: ${COMFYUI_DIR:-<not set>}"
  echo ""
  
  echo "Ports:"
  config_load_ports 2>/dev/null || true
  env | grep ^PORT_ | sort | sed 's/^/  /'
  echo ""
  
  echo "Features:"
  local features_yml
  features_yml="$(config_file 'features.yml')"
  if [[ -f "$features_yml" ]]; then
    grep -E "^[a-z].*: (true|false)" "$features_yml" | head -20 | sed 's/^/  /'
    echo "  ..."
  else
    echo "  <features.yml not found>"
  fi
}
