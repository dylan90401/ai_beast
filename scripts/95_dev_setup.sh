#!/usr/bin/env bash
# Bootstrap Python development environment for AI Beast
# Usage: ./scripts/95_dev_setup.sh [--apply]
# Follows Kryptos instructions: DRYRUN by default, portable paths

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Mode detection
parse_common_flags "${@:-}"

log_info "==> AI Beast: Dev Environment Setup"
log_info "    Mode: $(mode_label)"
log_info ""

#------------------------------------------------------------------------------
# Step 1: Check Python version
#------------------------------------------------------------------------------

log_info "[1/6] Checking Python version..."

if ! command_exists python3; then
  log_error "python3 not found. Install Python 3.11+ first."
  exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
  log_error "Python $PYTHON_VERSION found, but 3.11+ required"
  exit 1
fi
log_success "Python $PYTHON_VERSION"

#------------------------------------------------------------------------------
# Step 2: Check for virtual environment or pipx
#------------------------------------------------------------------------------

log_info "[2/6] Checking installation method..."

INSTALL_METHOD=""

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  log_success "Virtual environment detected: $VIRTUAL_ENV"
  INSTALL_METHOD="venv"
elif command_exists pipx; then
  log_success "pipx detected: $(command -v pipx)"
  INSTALL_METHOD="pipx"
else
  log_warn "No venv active and pipx not found."
  log_info "Choose installation method:"
  log_info "  Option 1: Create venv (recommended for development)"
  log_info "    python3 -m venv .venv"
  log_info "    source .venv/bin/activate"
  log_info "    ./scripts/95_dev_setup.sh --apply"
  log_info ""
  log_info "  Option 2: Install pipx (better for CLI tools)"
  log_info "    brew install pipx"
  log_info "    pipx ensurepath"
  log_info "    ./scripts/95_dev_setup.sh --apply"
  exit 1
fi

#------------------------------------------------------------------------------
# Step 3: Upgrade pip
#------------------------------------------------------------------------------

log_info "[3/6] Upgrading pip..."

if [[ "$INSTALL_METHOD" == "venv" ]]; then
  if [[ ${DRYRUN:-1} -eq 0 ]]; then
    pip3 install --upgrade pip
    log_success "pip upgraded"
  else
    log_dryrun "Would upgrade pip"
  fi
fi

#------------------------------------------------------------------------------
# Step 4: Install development dependencies
#------------------------------------------------------------------------------

log_info "[4/6] Installing development dependencies..."

DEV_PACKAGES=(
  "ruff"
  "pytest"
  "pytest-cov"
  "pyyaml"
  "click"
  "requests"
  "pydantic"
)

if [[ "$INSTALL_METHOD" == "venv" ]]; then
  if [[ ${DRYRUN:-1} -eq 0 ]]; then
    pip3 install "${DEV_PACKAGES[@]}"
    log_success "Installed packages via pip in venv"
  else
    log_dryrun "Would install: ${DEV_PACKAGES[*]}"
  fi
elif [[ "$INSTALL_METHOD" == "pipx" ]]; then
  if [[ ${DRYRUN:-1} -eq 0 ]]; then
    for pkg in "${DEV_PACKAGES[@]}"; do
      if pipx list 2>/dev/null | grep -q "package $pkg"; then
        log_info "  $pkg already installed"
      else
        pipx install "$pkg" || log_warn "Could not install $pkg via pipx"
      fi
    done
    log_success "Installed via pipx"
  else
    log_dryrun "Would install via pipx: ${DEV_PACKAGES[*]}"
  fi
fi

#------------------------------------------------------------------------------
# Step 5: Install project in editable mode
#------------------------------------------------------------------------------

log_info "[5/6] Installing project in editable mode..."

if [[ "$INSTALL_METHOD" == "venv" ]]; then
  if [[ ${DRYRUN:-1} -eq 0 ]]; then
    pip3 install -e "$BASE_DIR"
    log_success "Installed project in editable mode"
  else
    log_dryrun "Would install project with: pip3 install -e ."
  fi
else
  log_info "Skipping (pipx doesn't support editable installs)"
fi

#------------------------------------------------------------------------------
# Step 6: Verify installation
#------------------------------------------------------------------------------

log_info "[6/6] Verifying installation..."

TOOLS_OK=1

for tool in ruff pytest python3; do
  if command_exists "$tool"; then
    log_success "$tool: $(command -v "$tool")"
  else
    log_error "$tool not found in PATH"
    TOOLS_OK=0
  fi
done

if [[ $TOOLS_OK -eq 1 ]]; then
  log_success "All tools verified"
else
  log_warn "Some tools not found. Check your PATH or venv activation."
fi

#------------------------------------------------------------------------------
# Summary
#------------------------------------------------------------------------------

log_info ""
log_info "==> Setup complete"
log_info "    Method: $INSTALL_METHOD"
log_info ""
log_info "Next steps:"
log_info "  make check    # Run quality gates"
log_info "  make test     # Run tests"
log_info "  make fmt      # Format code"
log_info "  ./bin/beast preflight --verbose"
