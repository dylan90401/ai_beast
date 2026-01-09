#!/usr/bin/env bash
# 02_runtime_switch.sh — Switch container runtime (Colima/Docker/Podman)
set -euo pipefail

APPLY=0
RUNTIME=""
for arg in "${@:-}"; do
  [[ "$arg" == "--apply" ]] && APPLY=1
  [[ "$arg" == "colima" ]] && RUNTIME="colima"
  [[ "$arg" == "docker" || "$arg" == "docker_desktop" ]] && RUNTIME="docker_desktop"
  [[ "$arg" == "podman" ]] && RUNTIME="podman"
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[runtime] $*"; }
die(){ echo "[runtime] ERROR: $*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: $0 <runtime> [--apply]

Runtimes:
  colima         Colima (lightweight, recommended for Apple Silicon)
  docker         Docker Desktop
  podman         Podman (rootless)

Options:
  --apply  Actually switch runtime (default: DRYRUN)

Current runtime: $(grep -E "^export DOCKER_RUNTIME=" "$BASE_DIR/config/profiles.env" 2>/dev/null | cut -d'"' -f2 || echo "not set")

Examples:
  $0 colima              # Preview switch to Colima
  $0 colima --apply      # Switch to Colima and start it
  $0 docker --apply      # Switch to Docker Desktop
EOF
  exit 1
}

[[ -z "$RUNTIME" ]] && usage

# Check runtime is installed
check_runtime() {
  case "$1" in
    colima)
      command -v colima >/dev/null 2>&1 || die "Colima not installed. Install with: brew install colima"
      command -v docker >/dev/null 2>&1 || die "Docker CLI not installed. Install with: brew install docker"
      ;;
    docker_desktop)
      command -v docker >/dev/null 2>&1 || die "Docker not installed"
      ;;
    podman)
      command -v podman >/dev/null 2>&1 || die "Podman not installed. Install with: brew install podman"
      ;;
  esac
}

# Get current runtime
get_current() {
  local profiles="$BASE_DIR/config/profiles.env"
  [[ -f "$profiles" ]] || return
  grep -E "^export DOCKER_RUNTIME=" "$profiles" 2>/dev/null | cut -d'"' -f2 || echo ""
}

# Stop runtime
stop_runtime() {
  local rt="$1"
  log "Stopping $rt..."
  case "$rt" in
    colima)
      colima stop 2>/dev/null || true
      ;;
    docker_desktop)
      # Can't easily stop Docker Desktop from CLI
      log "Docker Desktop: close the app manually if needed"
      ;;
    podman)
      podman machine stop 2>/dev/null || true
      ;;
  esac
}

# Start runtime
start_runtime() {
  local rt="$1"
  log "Starting $rt..."
  case "$rt" in
    colima)
      # Get resource settings
      local cpus="${RUNTIME_COLIMA_CPUS:-6}"
      local mem="${RUNTIME_COLIMA_MEMORY:-30}"
      local disk="${RUNTIME_COLIMA_DISK:-80}"
      
      if colima status 2>/dev/null | grep -q "Running"; then
        log "Colima already running"
      else
        log "Starting Colima with $cpus CPUs, ${mem}GB RAM, ${disk}GB disk..."
        colima start --cpu "$cpus" --memory "$mem" --disk "$disk" --arch aarch64
      fi
      ;;
    docker_desktop)
      log "Docker Desktop: start the app if not running"
      # Try to start Docker Desktop on macOS
      if [[ "$(uname -s)" == "Darwin" ]]; then
        open -a "Docker" 2>/dev/null || log "Could not auto-start Docker Desktop"
      fi
      ;;
    podman)
      if ! podman machine info 2>/dev/null | grep -q "Running"; then
        podman machine start 2>/dev/null || podman machine init && podman machine start
      fi
      ;;
  esac
}

# Update config
update_config() {
  local rt="$1"
  local profiles="$BASE_DIR/config/profiles.env"
  
  if [[ -f "$profiles" ]]; then
    if grep -q "^export DOCKER_RUNTIME=" "$profiles"; then
      sed -i '' "s|^export DOCKER_RUNTIME=.*|export DOCKER_RUNTIME=\"$rt\"|" "$profiles"
    else
      echo "export DOCKER_RUNTIME=\"$rt\"" >> "$profiles"
    fi
  else
    cat > "$profiles" <<EOF
# lite | full | prodish
export AI_BEAST_PROFILE="full"

# Container runtime: colima | docker_desktop | podman
export DOCKER_RUNTIME="$rt"
EOF
  fi
  log "Updated $profiles"
}

# Main
check_runtime "$RUNTIME"
CURRENT=$(get_current)

if [[ "$RUNTIME" == "$CURRENT" ]]; then
  log "Already configured for $RUNTIME"
  if [[ "$APPLY" -eq 1 ]]; then
    start_runtime "$RUNTIME"
    log "Runtime $RUNTIME is ready"
  fi
  exit 0
fi

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would switch from ${CURRENT:-none} to $RUNTIME"
  log "Run with --apply to actually switch"
  exit 0
fi

log "Switching from ${CURRENT:-none} to $RUNTIME..."

# Stop old runtime
[[ -n "$CURRENT" ]] && stop_runtime "$CURRENT"

# Update config
update_config "$RUNTIME"

# Start new runtime
start_runtime "$RUNTIME"

log "Switched to $RUNTIME!"
log ""
log "Verify with: docker info"
log "Or run: ./bin/beast preflight"
