#!/usr/bin/env bash
# Configure Open WebUI after deployment
# This script sets up default configuration via the API
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BASE_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Source common functions
# shellcheck disable=SC1091
if [[ -f "$BASE_DIR/scripts/lib/common.sh" ]]; then
    source "$BASE_DIR/scripts/lib/common.sh"
else
    info() { echo "[INFO] $*"; }
    warn() { echo "[WARN] $*" >&2; }
    error() { echo "[ERROR] $*" >&2; }
fi

# Configuration
PORT_WEBUI="${PORT_WEBUI:-3000}"
WEBUI_URL="http://localhost:${PORT_WEBUI}"
MAX_WAIT=60

info "Configuring Open WebUI..."

# Wait for service to be ready
info "Waiting for Open WebUI to be ready..."
waited=0
while [[ $waited -lt $MAX_WAIT ]]; do
    if curl -sf "${WEBUI_URL}/health" >/dev/null 2>&1; then
        info "Open WebUI is ready"
        break
    fi
    sleep 2
    waited=$((waited + 2))
done

if [[ $waited -ge $MAX_WAIT ]]; then
    warn "Timeout waiting for Open WebUI - it may still be starting"
    exit 0
fi

# Check if we need to configure (first run)
info "Checking configuration status..."

# Configure default settings via API if available
# Note: These may require authentication if WEBUI_AUTH is enabled
configure_settings() {
    info "Attempting to set default configuration..."

    # Set default model preference
    curl -sf -X POST "${WEBUI_URL}/api/config" \
        -H "Content-Type: application/json" \
        -d '{
            "default_models": ["llama3.2:latest"],
            "rag_enabled": true,
            "web_search_enabled": true
        }' >/dev/null 2>&1 && info "Set default config" || warn "Could not set config (may require auth)"

    # Set system prompt
    curl -sf -X POST "${WEBUI_URL}/api/config/system" \
        -H "Content-Type: application/json" \
        -d '{
            "system_prompt": "You are a helpful AI assistant running on AI Beast. Be concise, accurate, and helpful."
        }' >/dev/null 2>&1 && info "Set system prompt" || warn "Could not set system prompt"
}

# Only configure if auth is disabled (for local development)
if [[ "${WEBUI_AUTH:-false}" == "false" ]]; then
    configure_settings
else
    info "Authentication enabled - skipping auto-configuration"
    info "Please configure Open WebUI manually at ${WEBUI_URL}"
fi

info "Open WebUI configuration complete"
info "Access at: ${WEBUI_URL}"
