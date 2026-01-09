#!/usr/bin/env bash
# Preflight checks for AI Beast
# Usage: ./scripts/00_preflight.sh [--verbose]
# Follows Kryptos instructions: DRYRUN by default, no hardcoded ports/paths

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export BASE_DIR

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Parse flags
parse_common_flags "${@:-}"

log_info "==> AI Beast Preflight Checks"
log_info "    BASE_DIR: $BASE_DIR"
log_info ""

# Check 1: Operating System
log_info "[1/8] Checking operating system..."
if is_macos; then
  OS_VERSION=$(sw_vers -productVersion)
  log_success "macOS $OS_VERSION"
elif is_linux; then
  OS_VERSION=$(uname -r)
  log_success "Linux $OS_VERSION"
else
  log_error "Unsupported operating system: $(uname -s)"
  exit 1
fi

# Check 2: Required commands
log_info "[2/8] Checking required commands..."
REQUIRED_COMMANDS=(git python3 docker)
MISSING_COMMANDS=()

for cmd in "${REQUIRED_COMMANDS[@]}"; do
  if command_exists "$cmd"; then
    VERSION=$("$cmd" --version 2>&1 | head -n1)
    [[ ${VERBOSE:-0} -eq 1 ]] && log_success "$cmd: $VERSION"
  else
    MISSING_COMMANDS+=("$cmd")
    log_error "$cmd: not found"
  fi
done

if [[ ${#MISSING_COMMANDS[@]} -gt 0 ]]; then
  log_error "Missing commands: ${MISSING_COMMANDS[*]}"
  log_info "Install with:"
  if is_macos; then
    log_info "  brew install ${MISSING_COMMANDS[*]}"
  else
    log_info "  apt install ${MISSING_COMMANDS[*]}"
  fi
  exit 1
fi

# Check 3: Python version
log_info "[3/8] Checking Python version..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
REQUIRED_VERSION="3.11"
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
  log_success "Python $PYTHON_VERSION (>= $REQUIRED_VERSION)"
else
  log_error "Python $PYTHON_VERSION (< $REQUIRED_VERSION required)"
  exit 1
fi

# Check 4: Docker status
log_info "[4/8] Checking Docker..."
if ! docker info >/dev/null 2>&1; then
  log_error "Docker daemon not running"
  log_info "Start Docker Desktop or run: colima start"
  exit 1
fi
log_success "Docker daemon running"

# Check 5: Configuration files
log_info "[5/8] Checking configuration files..."
CONFIG_FILES=(
  "config/paths.env"
  "config/ports.env"
  "config/features.yml"
)
MISSING_CONFIG=()

for file in "${CONFIG_FILES[@]}"; do
  if [[ -f "$BASE_DIR/$file" ]]; then
    [[ ${VERBOSE:-0} -eq 1 ]] && log_success "$file"
  else
    MISSING_CONFIG+=("$file")
    log_warn "$file: not found (will use example)"
  fi
done

if [[ ${#MISSING_CONFIG[@]} -gt 0 ]]; then
  log_info "Copy example files:"
  for file in "${MISSING_CONFIG[@]}"; do
    if [[ -f "$BASE_DIR/${file}.example" ]]; then
      log_info "  cp ${file}.example ${file}"
    fi
  done
fi

# Check 6: Required directories
log_info "[6/8] Checking directories..."
load_env "$BASE_DIR/config/paths.env"

REQUIRED_DIRS=(
  "$BASE_DIR/scripts"
  "$BASE_DIR/config"
  "$BASE_DIR/compose"
)

for dir in "${REQUIRED_DIRS[@]}"; do
  if [[ -d "$dir" ]]; then
    [[ ${VERBOSE:-0} -eq 1 ]] && log_success "$dir"
  else
    log_error "$dir: not found"
    exit 1
  fi
done

# Check 7: Docker Compose
log_info "[7/8] Checking Docker Compose..."
if docker compose version >/dev/null 2>&1; then
  COMPOSE_VERSION=$(docker compose version --short)
  log_success "Docker Compose $COMPOSE_VERSION"
  
  # Validate compose file
  if [[ -f "$BASE_DIR/compose/base.yml" ]]; then
    if docker compose -f "$BASE_DIR/compose/base.yml" config >/dev/null 2>&1; then
      [[ ${VERBOSE:-0} -eq 1 ]] && log_success "compose/base.yml valid"
    else
      log_error "compose/base.yml invalid"
      exit 1
    fi
  fi
else
  log_error "Docker Compose not available"
  exit 1
fi

# Check 8: Python packages
log_info "[8/8] Checking Python packages..."
REQUIRED_PACKAGES=(pytest ruff pyyaml)
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
  if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
    [[ ${VERBOSE:-0} -eq 1 ]] && log_success "$pkg"
  else
    MISSING_PACKAGES+=("$pkg")
    log_warn "$pkg: not installed"
  fi
done

if [[ ${#MISSING_PACKAGES[@]} -gt 0 ]]; then
  log_info "Install with: pip install ${MISSING_PACKAGES[*]}"
fi

log_info ""
log_success "Preflight checks complete"
log_info "Next steps:"
log_info "  ./bin/beast init --apply       # Initialize environment"
log_info "  ./bin/beast bootstrap --apply  # Bootstrap macOS"
log_info "  make check                     # Run quality gates"
