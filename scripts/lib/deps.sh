#!/usr/bin/env bash
s#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/lib/ux.sh"

detect_os() {
  local u
  u="$(uname -s | tr '[:upper:]' '[:lower:]')"
  case "$u" in
    darwin*) echo "macos" ;;
    linux*)  echo "linux" ;;
    *) echo "unknown" ;;
  esac
}

ensure_python3() {
  have python3 || die "python3 not found. Install Python 3.11+."
}

ensure_brew_macos() {
  have brew || die "Homebrew not found. Install from https://brew.sh"
}

ensure_shellcheck() {
  if ! have shellcheck; then
    ux_warn "shellcheck not found."
  fi
}

ensure_shfmt() {
  if ! have shfmt; then
    ux_warn "shfmt not found."
  fi
}

ensure_docker_cli() {
  have docker || die "docker CLI not found."
}

ensure_colima() {
  have colima || return 1
  return 0
}

  # Official installer
  run /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Ensure brew is on PATH for this shell + future shells
  if [[ -x /opt/homebrew/bin/brew ]]; then
    # zsh default
    run /bin/bash -lc "grep -q 'brew shellenv' \"$HOME/.zprofile\" 2>/dev/null || echo 'eval \"$(/opt/homebrew/bin/brew shellenv)\"' >> \"$HOME/.zprofile\""
    # current process best-effort
    # shellcheck disable=SC1091
    eval "$(/opt/homebrew/bin/brew shellenv)" || true
  fi
}

deps_brew_update(){
  have_cmd brew || return 0
  try_run brew update
}

deps_brew_install_formulae(){
  have_cmd brew || { warn "brew not found; skipping brew formula installs"; return 0; }
  local pkgs=("$@")
  [[ ${#pkgs[@]} -gt 0 ]] || return 0
  for p in "${pkgs[@]}"; do
    if brew list "$p" >/dev/null 2>&1; then
      log "brew already: $p"
      continue
    fi
    run brew install "$p"
  done
}

deps_brew_install_casks(){
  have_cmd brew || { warn "brew not found; skipping brew cask installs"; return 0; }
  local pkgs=("$@")
  [[ ${#pkgs[@]} -gt 0 ]] || return 0
  for p in "${pkgs[@]}"; do
    if brew list --cask "$p" >/dev/null 2>&1; then
      log "brew(cask) already: $p"
      continue
    fi
    run brew install --cask "$p"
  done
}

deps_python_venv_ensure(){
  local venv_dir="$1"
  require_cmd python3
  if [[ -d "$venv_dir" ]]; then
    log "Venv exists: $venv_dir"
    return 0
  fi
  run python3 -m venv "$venv_dir"
}

deps_python_pip_upgrade(){
  local venv_dir="$1"
  [[ -d "$venv_dir" ]] || die "Venv missing: $venv_dir"
  if [[ "${APPLY:-0}" -ne 1 ]]; then
    log "DRYRUN: (venv) pip install -U pip wheel setuptools"
    return 0
  fi
  # shellcheck disable=SC1090
  source "$venv_dir/bin/activate"
  python -m pip install -U pip wheel setuptools
  deactivate || true
}

deps_python_pip_install_requirements(){
  local venv_dir="$1" req_file="$2"
  [[ -f "$req_file" ]] || die "requirements.txt not found: $req_file"
  if [[ "${APPLY:-0}" -ne 1 ]]; then
    log "DRYRUN: (venv) pip install -r $req_file"
    return 0
  fi
  # shellcheck disable=SC1090
  source "$venv_dir/bin/activate"
  python -m pip install -r "$req_file"
  deactivate || true
}
install_macos_deps() {
  ensure_brew_macos
  ux_info "Installing macOS deps via brew (idempotent)…"
  brew install python@3.11 docker docker-compose colima shellcheck shfmt >/dev/null || true
  ux_ok "brew deps installed/verified"
}

install_linux_deps() {
  ux_info "Linux deps: install docker + python3 + shellcheck/shfmt as appropriate."
  ux_warn "Linux installer is intentionally conservative; customize scripts/21_bootstrap_linux.sh for your distro."
}

ensure_runtime_tools() {
  local os
  os="$(detect_os)"
  case "$os" in
    macos) install_macos_deps ;;
    linux) install_linux_deps ;;
    *) die "Unsupported OS: $os" ;;
  esac
}