#!/usr/bin/env bash
# runtime.sh — Container runtime abstraction (Docker vs Colima)
# AI Beast / Kryptos
# Supports: colima | docker_desktop | podman
#
# Usage:
#   source scripts/lib/runtime.sh
#   runtime_ensure   # Start/verify runtime
#   runtime_info     # Show runtime details

set -euo pipefail

# Ensure we have common helpers
SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

# Default resource allocations for Colima
RUNTIME_COLIMA_CPUS="${RUNTIME_COLIMA_CPUS:-6}"
RUNTIME_COLIMA_MEMORY="${RUNTIME_COLIMA_MEMORY:-12}"
RUNTIME_COLIMA_DISK="${RUNTIME_COLIMA_DISK:-80}"
RUNTIME_COLIMA_ARCH="${RUNTIME_COLIMA_ARCH:-aarch64}"

# ─────────────────────────────────────────────────────────────
# Detection
# ─────────────────────────────────────────────────────────────

# Detect which container runtime is available/preferred
runtime_detect() {
  local want="${DOCKER_RUNTIME:-auto}"
  
  # If explicitly set, validate and return
  case "$want" in
    colima)
      if command_exists colima && command_exists docker; then
        echo "colima"
        return 0
      fi
      log_warn "DOCKER_RUNTIME=colima but colima/docker not found"
      ;;
    docker_desktop|docker)
      if command_exists docker; then
        echo "docker_desktop"
        return 0
      fi
      log_warn "DOCKER_RUNTIME=$want but docker not found"
      ;;
    podman)
      if command_exists podman; then
        echo "podman"
        return 0
      fi
      log_warn "DOCKER_RUNTIME=podman but podman not found"
      ;;
    auto|"")
      # Auto-detect: prefer Colima on macOS Apple Silicon
      ;;
    *)
      log_warn "Unknown DOCKER_RUNTIME='$want'. Using auto-detect."
      ;;
  esac

  # Auto-detection priority:
  # 1. Colima (macOS preferred for Apple Silicon)
  # 2. Docker Desktop
  # 3. Podman
  if is_macos && command_exists colima && command_exists docker; then
    echo "colima"
  elif command_exists docker; then
    echo "docker_desktop"
  elif command_exists podman; then
    echo "podman"
  else
    echo "none"
  fi
}

# Get human-readable runtime name
runtime_name() {
  local rt="${1:-$(runtime_detect)}"
  case "$rt" in
    colima) echo "Colima" ;;
    docker_desktop) echo "Docker Desktop" ;;
    podman) echo "Podman" ;;
    none) echo "None (not installed)" ;;
    *) echo "$rt" ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────

# Check if Docker daemon is reachable
runtime_docker_ready() {
  command_exists docker && docker info >/dev/null 2>&1
}

# Check if Colima is running
runtime_colima_running() {
  command_exists colima && colima status >/dev/null 2>&1
}

# Check if Podman is ready
runtime_podman_ready() {
  command_exists podman && podman info >/dev/null 2>&1
}

# Check if any runtime is ready
runtime_is_ready() {
  local rt="${1:-$(runtime_detect)}"
  case "$rt" in
    colima)
      runtime_colima_running && runtime_docker_ready
      ;;
    docker_desktop)
      runtime_docker_ready
      ;;
    podman)
      runtime_podman_ready
      ;;
    *)
      return 1
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# Start/Stop
# ─────────────────────────────────────────────────────────────

# Start Colima with configured resources
runtime_start_colima() {
  if ! command_exists colima; then
    log_error "Colima not installed. Install with: brew install colima"
    return 1
  fi
  
  if runtime_colima_running; then
    log_info "Colima already running"
    return 0
  fi
  
  log_info "Starting Colima (cpu=$RUNTIME_COLIMA_CPUS mem=${RUNTIME_COLIMA_MEMORY}G disk=${RUNTIME_COLIMA_DISK}G)..."
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would start colima with: colima start --cpu $RUNTIME_COLIMA_CPUS --memory $RUNTIME_COLIMA_MEMORY --disk $RUNTIME_COLIMA_DISK"
    return 0
  fi
  
  colima start \
    --cpu "$RUNTIME_COLIMA_CPUS" \
    --memory "$RUNTIME_COLIMA_MEMORY" \
    --disk "$RUNTIME_COLIMA_DISK" \
    --arch "$RUNTIME_COLIMA_ARCH" \
    --vm-type vz \
    --mount-type virtiofs \
    2>&1 | while read -r line; do log_info "  $line"; done
  
  # Wait for docker to be ready
  local retries=30
  while [[ $retries -gt 0 ]]; do
    if runtime_docker_ready; then
      log_success "Colima started successfully"
      return 0
    fi
    sleep 1
    ((retries--))
  done
  
  log_error "Colima started but Docker not responding"
  return 1
}

# Stop Colima
runtime_stop_colima() {
  if ! runtime_colima_running; then
    log_info "Colima not running"
    return 0
  fi
  
  log_info "Stopping Colima..."
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would stop colima"
    return 0
  fi
  
  colima stop
  log_success "Colima stopped"
}

# Ensure runtime is started and ready
runtime_ensure() {
  local rt
  rt="$(runtime_detect)"
  
  log_info "Container runtime: $(runtime_name "$rt") (DOCKER_RUNTIME=${DOCKER_RUNTIME:-auto})"
  
  case "$rt" in
    colima)
      runtime_start_colima || return 1
      ;;
    docker_desktop)
      if ! runtime_docker_ready; then
        log_warn "Docker Desktop not running. Please start Docker Desktop manually."
        log_info "  On macOS: open -a Docker"
        return 1
      fi
      log_success "Docker Desktop ready"
      ;;
    podman)
      if ! runtime_podman_ready; then
        log_info "Starting Podman machine..."
        if [[ "${DRYRUN:-1}" -eq 0 ]]; then
          podman machine start 2>/dev/null || podman machine init && podman machine start
        else
          log_dryrun "Would start podman machine"
        fi
      fi
      log_success "Podman ready"
      ;;
    none)
      log_error "No container runtime found!"
      log_info "Install options:"
      log_info "  • brew install colima docker docker-compose  (recommended for macOS)"
      log_info "  • brew install --cask docker  (Docker Desktop)"
      log_info "  • brew install podman  (alternative)"
      return 1
      ;;
    *)
      log_error "Unknown runtime: $rt"
      return 1
      ;;
  esac
  
  return 0
}

# ─────────────────────────────────────────────────────────────
# Info
# ─────────────────────────────────────────────────────────────

# Display runtime information
runtime_info() {
  local rt
  rt="$(runtime_detect)"
  
  echo "Container Runtime Status"
  echo "========================"
  echo "Selected runtime: $(runtime_name "$rt")"
  echo "DOCKER_RUNTIME env: ${DOCKER_RUNTIME:-auto}"
  echo ""
  
  # Check available runtimes
  echo "Available runtimes:"
  if command_exists colima; then
    local colima_status="stopped"
    runtime_colima_running && colima_status="running"
    echo "  ✓ Colima ($colima_status)"
    if runtime_colima_running; then
      colima status 2>/dev/null | sed 's/^/    /'
    fi
  else
    echo "  ✗ Colima (not installed)"
  fi
  
  if command_exists docker; then
    local docker_status="not responding"
    runtime_docker_ready && docker_status="ready"
    echo "  ✓ Docker CLI ($docker_status)"
    if runtime_docker_ready; then
      docker version --format "    Server: {{.Server.Version}}" 2>/dev/null || true
    fi
  else
    echo "  ✗ Docker CLI (not installed)"
  fi
  
  if command_exists podman; then
    local podman_status="not responding"
    runtime_podman_ready && podman_status="ready"
    echo "  ✓ Podman ($podman_status)"
  else
    echo "  ✗ Podman (not installed)"
  fi
  
  echo ""
  echo "Recommended setup for macOS (Apple Silicon):"
  echo "  brew install colima docker docker-compose"
  echo "  export DOCKER_RUNTIME=colima  # or add to ~/.zshrc"
}

# ─────────────────────────────────────────────────────────────
# Compose helpers
# ─────────────────────────────────────────────────────────────

# Get the appropriate compose command
runtime_compose_cmd() {
  if command_exists "docker-compose"; then
    echo "docker-compose"
  elif command_exists docker && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  else
    echo ""
  fi
}

# Run docker compose with runtime ensured
runtime_compose() {
  runtime_ensure || return 1
  
  local compose_cmd
  compose_cmd="$(runtime_compose_cmd)"
  
  if [[ -z "$compose_cmd" ]]; then
    log_error "No docker compose found. Install with: brew install docker-compose"
    return 1
  fi
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would run: $compose_cmd $*"
    return 0
  fi
  
  # shellcheck disable=SC2086
  $compose_cmd "$@"
}
