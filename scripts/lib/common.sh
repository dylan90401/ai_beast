#!/usr/bin/env bash
# common.sh — shared helpers for AI Beast scripts
# Follows Kryptos instructions: DRYRUN by default, no hardcoded ports/paths

set -euo pipefail

# Ensure BASE_DIR is set
if [[ -z "${BASE_DIR:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
  export BASE_DIR
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
  echo -e "${GREEN}[✓]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_dryrun() {
  echo -e "${YELLOW}[DRYRUN]${NC} $*"
}

# Legacy aliases for compatibility
log()  { log_info "$@"; }
warn() { log_warn "$@"; }
die()  { log_error "$@"; exit 1; }

# Check if command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Legacy alias
have_cmd() { command_exists "$@"; }

# Check if running on macOS
is_macos() {
  [[ "$(uname -s)" == "Darwin" ]]
}

# Legacy alias
is_darwin() { is_macos; }

# Check if running on Linux
is_linux() {
  [[ "$(uname -s)" == "Linux" ]]
}

# Load environment file
load_env() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$env_file"
    set +a
  fi
}

# Legacy alias
load_env_if_exists() { load_env "$@"; }

# Get mode label (DRYRUN vs APPLY)
mode_label() {
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    echo "DRYRUN"
  else
    echo "APPLY"
  fi
}

# Parse common flags into DRYRUN/VERBOSE
parse_common_flags() {
  DRYRUN=1
  VERBOSE=0
  for arg in "${@:-}"; do
    case "$arg" in
      --apply) DRYRUN=0 ;;
      --dry-run) DRYRUN=1 ;;
      --verbose) VERBOSE=1 ;;
    esac
  done
  export DRYRUN VERBOSE
}

# Confirm action in APPLY mode
confirm_apply() {
  local message="$1"
  if [[ "${DRYRUN:-1}" -eq 0 ]]; then
    log_warn "APPLY MODE: $message"
    read -r -p "Continue? [y/N] " response
    case "$response" in
      [yY][eE][sS]|[yY])
        return 0
        ;;
      *)
        log_info "Aborted"
        return 1
        ;;
    esac
  else
    log_dryrun "$message"
    return 0
  fi
}

# Run command with DRYRUN support
run() {
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would run: $*"
  else
    log_info "Running: $*"
    "$@"
  fi
}

# Run command with DRYRUN support (never exits script)
run_cmd() { run "$@"; }

# Try run: never exits the script; returns 0/1
try_run() {
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would try: $*"
    return 0
  else
    log_info "Trying: $*"
    if "$@"; then
      return 0
    else
      log_warn "Command failed (continuing): $*"
      return 1
    fi
  fi
}

# Check required commands
require_commands() {
  local missing=()
  for cmd in "$@"; do
    if ! command_exists "$cmd"; then
      missing+=("$cmd")
    fi
  done
  
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing required commands: ${missing[*]}"
    return 1
  fi
  return 0
}

# Legacy alias
require_cmd() {
  require_commands "$@"
}

# Load config files in order
load_beast_config() {
  load_env "$BASE_DIR/config/paths.env"
  load_env "$BASE_DIR/config/ports.env"
  load_env "$BASE_DIR/config/features.env"
  load_env "$BASE_DIR/config/ai-beast.env"
  load_env "$BASE_DIR/.env"
}
