#!/usr/bin/env bash
# health.sh — Health check and monitoring helpers
# AI Beast / Kryptos
#
# Provides service health checks, port scanning, and system diagnostics.

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"

# ─────────────────────────────────────────────────────────────
# Port Checks
# ─────────────────────────────────────────────────────────────

# Check if port is open (TCP)
health_port_open() {
  local host="${1:-127.0.0.1}"
  local port="$2"
  local timeout="${3:-2}"
  
  if command_exists nc; then
    nc -z -w "$timeout" "$host" "$port" 2>/dev/null
  elif command_exists timeout; then
    timeout "$timeout" bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null
  else
    # Fallback: try /dev/tcp
    (echo >/dev/tcp/"$host"/"$port") 2>/dev/null
  fi
}

# Check HTTP endpoint
health_http_ok() {
  local url="$1"
  local timeout="${2:-5}"
  local expected="${3:-200}"
  
  if ! command_exists curl; then
    log_warn "curl not found for HTTP health check"
    return 1
  fi
  
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$timeout" "$url" 2>/dev/null || echo "000")
  
  [[ "$status" == "$expected" ]]
}

# Check if process is running
health_process_running() {
  local pattern="$1"
  pgrep -f "$pattern" >/dev/null 2>&1
}

# ─────────────────────────────────────────────────────────────
# Service Health Definitions
# ─────────────────────────────────────────────────────────────

# Load ports from config
health_load_ports() {
  local ports_env="${BASE_DIR:-$(pwd)}/config/ports.env"
  if [[ -f "$ports_env" ]]; then
    # shellcheck source=/dev/null
    source "$ports_env"
  fi
}

# Define service health checks
# Format: name:type:target
# Types: port, http, process
health_services() {
  health_load_ports
  
  cat << EOF
ollama:port:${PORT_OLLAMA:-11434}
comfyui:port:${PORT_COMFYUI:-8188}
dashboard:port:${PORT_DASHBOARD:-8787}
qdrant:port:${PORT_QDRANT:-6333}
webui:port:${PORT_WEBUI:-3000}
n8n:port:${PORT_N8N:-5678}
uptime_kuma:port:${PORT_KUMA:-3001}
searxng:port:${PORT_SEARXNG:-8088}
minio:port:${PORT_MINIO:-9001}
flowise:port:${PORT_FLOWISE:-3003}
langflow:port:${PORT_LANGFLOW:-7860}
speech_api:port:${PORT_SPEECH_API:-9977}
EOF
}

# ─────────────────────────────────────────────────────────────
# Health Checks
# ─────────────────────────────────────────────────────────────

# Check single service health
health_check_service() {
  local name="$1"
  local type="$2"
  local target="$3"
  
  case "$type" in
    port)
      health_port_open "127.0.0.1" "$target"
      ;;
    http)
      health_http_ok "$target"
      ;;
    process)
      health_process_running "$target"
      ;;
    *)
      log_warn "Unknown health check type: $type"
      return 1
      ;;
  esac
}

# Check all services and return status
health_check_all() {
  local format="${1:-text}"
  local results=()
  local healthy=0
  local unhealthy=0
  
  while IFS=: read -r name type target; do
    [[ -z "$name" ]] && continue
    
    if health_check_service "$name" "$type" "$target"; then
      results+=("$name:healthy:$target")
      ((healthy++))
    else
      results+=("$name:unhealthy:$target")
      ((unhealthy++))
    fi
  done < <(health_services)
  
  case "$format" in
    json)
      echo "{"
      echo "  \"healthy\": $healthy,"
      echo "  \"unhealthy\": $unhealthy,"
      echo "  \"services\": {"
      local first=1
      for r in "${results[@]}"; do
        IFS=: read -r name status target <<< "$r"
        [[ $first -eq 0 ]] && echo ","
        first=0
        echo -n "    \"$name\": {\"status\": \"$status\", \"target\": \"$target\"}"
      done
      echo ""
      echo "  }"
      echo "}"
      ;;
    text)
      echo "Service Health Check"
      echo "===================="
      for r in "${results[@]}"; do
        IFS=: read -r name status target <<< "$r"
        if [[ "$status" == "healthy" ]]; then
          printf "  ✓ %-15s %s\n" "$name" "(port $target)"
        else
          printf "  ✗ %-15s %s\n" "$name" "(port $target not responding)"
        fi
      done
      echo ""
      echo "Summary: $healthy healthy, $unhealthy unhealthy"
      ;;
    simple)
      for r in "${results[@]}"; do
        IFS=: read -r name status _ <<< "$r"
        echo "$name:$status"
      done
      ;;
  esac
  
  [[ $unhealthy -eq 0 ]]
}

# ─────────────────────────────────────────────────────────────
# System Diagnostics
# ─────────────────────────────────────────────────────────────

# Check disk space
health_disk_usage() {
  local path="${1:-/}"
  local threshold="${2:-90}"
  
  local usage
  usage=$(df -h "$path" | awk 'NR==2 {print $5}' | tr -d '%')
  
  echo "Disk usage at $path: ${usage}%"
  
  if [[ "$usage" -ge "$threshold" ]]; then
    log_warn "Disk usage above ${threshold}%!"
    return 1
  fi
  return 0
}

# Check memory
health_memory_usage() {
  if is_macos; then
    # macOS memory check
    local pages_free pages_inactive pages_speculative page_size
    pages_free=$(vm_stat | awk '/Pages free/ {print $3}' | tr -d '.')
    pages_inactive=$(vm_stat | awk '/Pages inactive/ {print $3}' | tr -d '.')
    pages_speculative=$(vm_stat | awk '/Pages speculative/ {print $3}' | tr -d '.')
    page_size=$(pagesize)
    
    local free_mb=$(( (pages_free + pages_inactive + pages_speculative) * page_size / 1024 / 1024 ))
    local total_mb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 ))
    local used_mb=$(( total_mb - free_mb ))
    local pct=$(( used_mb * 100 / total_mb ))
    
    echo "Memory: ${used_mb}MB / ${total_mb}MB (${pct}% used)"
  else
    # Linux memory check
    free -h | awk 'NR==2 {printf "Memory: %s / %s (%s used)\n", $3, $2, $3/$2*100"%"}'
  fi
}

# Check Docker/Colima status
health_docker_status() {
  echo "Docker Status"
  echo "============="
  
  if ! command_exists docker; then
    echo "  Docker CLI: not installed"
    return 1
  fi
  
  echo "  Docker CLI: installed"
  
  if docker info >/dev/null 2>&1; then
    echo "  Docker daemon: running"
    docker info 2>/dev/null | grep -E "Server Version|Storage Driver|Operating System" | sed 's/^/  /'
  else
    echo "  Docker daemon: not running"
    
    if command_exists colima; then
      echo "  Colima: $(colima status 2>/dev/null | head -1 || echo 'not running')"
      echo "  Start with: colima start"
    fi
    return 1
  fi
  
  return 0
}

# ─────────────────────────────────────────────────────────────
# Full Diagnostics
# ─────────────────────────────────────────────────────────────

# Run full system diagnostics
health_diagnostics() {
  echo "AI Beast System Diagnostics"
  echo "==========================="
  echo ""
  
  echo "System Info"
  echo "-----------"
  echo "  OS: $(uname -s) $(uname -r)"
  echo "  Arch: $(uname -m)"
  if is_macos; then
    echo "  macOS: $(sw_vers -productVersion)"
  fi
  echo ""
  
  echo "Resources"
  echo "---------"
  health_memory_usage
  health_disk_usage "${BASE_DIR:-/}"
  echo ""
  
  health_docker_status
  echo ""
  
  health_check_all text
}

# Quick health probe (for scripts)
health_probe() {
  local service="$1"
  
  while IFS=: read -r name type target; do
    [[ "$name" == "$service" ]] || continue
    health_check_service "$name" "$type" "$target"
    return $?
  done < <(health_services)
  
  # Service not found in definitions
  return 1
}

# Wait for service to be healthy
health_wait_for() {
  local service="$1"
  local timeout="${2:-60}"
  local interval="${3:-2}"
  
  log_info "Waiting for $service to be healthy (timeout: ${timeout}s)..."
  
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    if health_probe "$service"; then
      log_success "$service is healthy"
      return 0
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  
  log_error "$service did not become healthy within ${timeout}s"
  return 1
}
