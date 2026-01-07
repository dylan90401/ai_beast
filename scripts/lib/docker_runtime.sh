#!/usr/bin/env bash
set -euo pipefail

# docker_runtime.sh — choose and (optionally) boot a Docker runtime on macOS.
#
# Runtime values:
#   - colima
#   - docker_desktop

docker_runtime_choice(){
  local want="${DOCKER_RUNTIME:-}"
  if [[ -n "$want" ]]; then
    case "$want" in
      colima|docker_desktop) echo "$want"; return 0 ;;
      *) warn "Unknown DOCKER_RUNTIME='$want' (use: colima|docker_desktop). Falling back to auto." ;;
    esac
  fi

  # Colima-first behavior on Apple Silicon/macOS.
  if have_cmd colima; then
    echo "colima"; return 0
  fi
  echo "docker_desktop"
}

docker_runtime_hint(){
  local rt; rt="$(docker_runtime_choice)"
  case "$rt" in
    colima) echo "Colima" ;;
    docker_desktop) echo "Docker Desktop" ;;
    *) echo "$rt" ;;
  esac
}

docker_runtime_is_ready(){
  have_cmd docker || return 1
  docker info >/dev/null 2>&1
}

docker_runtime_start_colima(){
  require_cmd colima
  require_cmd docker

  if colima status >/dev/null 2>&1; then
    return 0
  fi

  # Avoid hardcoding resources; Colima defaults are fine for v17.
  run colima start
}

docker_runtime_ensure(){
  # Ensures "docker" can talk to an engine.
  local rt; rt="$(docker_runtime_choice)"
  log "Docker runtime: $(docker_runtime_hint) (DOCKER_RUNTIME=${DOCKER_RUNTIME:-auto})"

  case "$rt" in
    colima)
      if ! have_cmd docker; then
        warn "docker CLI not found. Install via Homebrew (docker, docker-compose) or Docker Desktop."
        return 1
      fi
      if ! have_cmd colima; then
        warn "colima not found. Install via Homebrew: brew install colima"
        return 1
      fi
      docker_runtime_start_colima
      ;;
    docker_desktop)
      # We can't reliably start the GUI app here; just validate connectivity.
      require_cmd docker
      ;;
    *)
      warn "Unknown runtime '$rt'"; return 1
      ;;
  esac

  if docker_runtime_is_ready; then
    log "Docker engine reachable."
    return 0
  fi

  warn "Docker engine not reachable. If using Docker Desktop, open the app and wait for it to finish starting."
  return 1
}
