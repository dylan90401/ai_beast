#!/usr/bin/env bash
# Import recommended models for Open WebUI
# This script pulls commonly used models via Ollama
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BASE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

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
PORT_OLLAMA="${PORT_OLLAMA:-11434}"
OLLAMA_URL="http://localhost:${PORT_OLLAMA}"

# Default models to pull
DEFAULT_MODELS=(
    "llama3.2:latest"
    "nomic-embed-text"
)

# Optional models (only pulled if requested)
OPTIONAL_MODELS=(
    "llama3.2:1b"
    "mistral:latest"
    "codellama:7b"
    "phi3:latest"
)

info "Importing models for Open WebUI..."

# Check if Ollama is running
if ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    warn "Ollama is not running at ${OLLAMA_URL}"
    warn "Please start Ollama first: ollama serve"
    exit 1
fi

# Function to pull a model
pull_model() {
    local model="$1"
    info "Pulling model: ${model}..."

    # Check if already downloaded
    if curl -sf "${OLLAMA_URL}/api/tags" | grep -q "\"name\":\"${model}\""; then
        info "  Model ${model} already available"
        return 0
    fi

    # Pull the model
    if curl -sf -X POST "${OLLAMA_URL}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"${model}\"}" >/dev/null 2>&1; then
        info "  Model ${model} pulled successfully"
    else
        warn "  Failed to pull ${model}"
        return 1
    fi
}

# Pull default models
info "Pulling default models..."
for model in "${DEFAULT_MODELS[@]}"; do
    pull_model "$model" || true
done

# Check for --all flag to pull optional models
if [[ "${1:-}" == "--all" ]]; then
    info "Pulling optional models..."
    for model in "${OPTIONAL_MODELS[@]}"; do
        pull_model "$model" || true
    done
fi

# List available models
info "Available models:"
curl -sf "${OLLAMA_URL}/api/tags" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        name = m.get('name', 'unknown')
        size = m.get('size', 0) / (1024**3)
        print(f'  - {name} ({size:.1f} GB)')
except:
    print('  Unable to list models')
" 2>/dev/null || warn "Could not list models"

info "Model import complete"
info ""
info "To pull additional models, run:"
info "  ollama pull <model-name>"
info ""
info "Recommended models for different use cases:"
info "  - Chat: llama3.2:latest, mistral:latest"
info "  - Code: codellama:7b, deepseek-coder:6.7b"
info "  - Embeddings: nomic-embed-text, mxbai-embed-large"
info "  - Small/Fast: llama3.2:1b, phi3:mini"
